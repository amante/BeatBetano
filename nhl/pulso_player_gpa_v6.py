"""NHL player goals, assists and points rate model, version 6.

Research model: separate goal and assist intensities per 60 player minutes.
Points are derived exactly as goals + assists. No betting odds or current-game
outcomes enter the forecast. Recency methods are scored out of sample before
any one is selected for production.
"""
import argparse
from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path

from nhl.pulso_player_v3 import SEASONS, TEAMS, build

METHODS = ("historical", "recent10", "ewma")
EVENTS = ("goals", "assists")
SEASON_PRIOR_MINUTES = 600.0
RECENT_PRIOR_MINUTES = 300.0
EWMA_PRIOR_MINUTES = 240.0
EWMA_DECAY = 0.85


def _finite_nonnegative(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid " + label)
    return float(value)


def validate_gpa_rows(rows):
    seen = set()
    result = []
    for row in rows:
        required = ("game_id", "date", "player_id", "team", "opponent",
                    "toi_minutes", "goals", "assists", "points")
        if any(row.get(key) in (None, "") for key in required):
            raise ValueError("Missing NHL G/A/P game-log field")
        day = date.fromisoformat(str(row["date"])).isoformat()
        key = (str(row["game_id"]), str(row["player_id"]))
        if key in seen:
            raise ValueError("Duplicate NHL player game")
        seen.add(key)
        toi = _finite_nonnegative(row["toi_minutes"], "player TOI")
        goals = _finite_nonnegative(row["goals"], "goals")
        assists = _finite_nonnegative(row["assists"], "assists")
        points = _finite_nonnegative(row["points"], "points")
        if toi <= 0 or any(int(value) != value for value in (goals, assists, points)):
            raise ValueError("Invalid NHL player exposure or count")
        if points != goals + assists:
            raise ValueError("NHL points must equal goals plus assists")
        result.append({**row, "game_id": str(row["game_id"]),
                       "player_id": str(row["player_id"]), "date": day,
                       "toi_minutes": toi, "goals": int(goals),
                       "assists": int(assists), "points": int(points)})
    return sorted(result, key=lambda row: (row["date"], row["game_id"], row["player_id"]))


def _rate_per60(rows, event, decay=None):
    if not rows:
        return 0.0
    weighted_count = 0.0
    weighted_minutes = 0.0
    for index, row in enumerate(rows):
        weight = 1.0 if decay is None else decay ** (len(rows) - index - 1)
        weighted_count += weight * row[event]
        weighted_minutes += weight * row["toi_minutes"]
    return 60.0 * weighted_count / weighted_minutes if weighted_minutes else 0.0


def _posterior_rate(rows, event, prior_rate, prior_minutes):
    minutes = sum(row["toi_minutes"] for row in rows)
    count = sum(row[event] for row in rows)
    denominator = minutes + prior_minutes
    if denominator <= 0:
        return 0.0
    return 60.0 * (count + prior_rate * prior_minutes / 60.0) / denominator


def _poisson_probability_at_least_one(expected_count):
    if expected_count < 0 or not math.isfinite(expected_count):
        raise ValueError("Invalid expected player count")
    return -math.expm1(-expected_count)


def _last_event_gap(history, event, target_date):
    scored = [row for row in history if row[event] > 0]
    if not scored:
        return {"games_since": None, "days_since": None}
    last = scored[-1]
    games_since = sum(1 for row in history if row["date"] > last["date"])
    return {
        "games_since": games_since,
        "days_since": (date.fromisoformat(target_date) -
                       date.fromisoformat(last["date"])).days,
    }


def project(history, target, position, peer_rates):
    """Project a player using prior rows only; target contains identity/context."""
    target_date = date.fromisoformat(target["date"]).isoformat()
    prior = [row for row in history if row["date"] < target_date]
    if len(prior) < 10:
        return {"status": "insufficient_player_history", "games": len(prior),
                "projection": None}
    recent = prior[-10:]
    projected_toi = sum(row["toi_minutes"] for row in recent) / len(recent)
    if projected_toi <= 0:
        raise ValueError("Cannot project player with zero recent TOI")
    rates = {}
    for event in EVENTS:
        peer = peer_rates.get(position, {}).get(event, 0.0)
        historical_rate = _posterior_rate(prior, event, peer, SEASON_PRIOR_MINUTES)
        rates[event] = {
            "historical": historical_rate,
            "recent10": _posterior_rate(recent, event, historical_rate, RECENT_PRIOR_MINUTES),
            "ewma": _posterior_rate(prior, event, historical_rate, EWMA_PRIOR_MINUTES)
                    if len(prior) < 2 else
                    _posterior_rate_weighted(prior, event, historical_rate,
                                             EWMA_PRIOR_MINUTES, EWMA_DECAY),
        }
    methods = {}
    for method in METHODS:
        expected = {
            event: rates[event][method] * projected_toi / 60.0
            for event in EVENTS
        }
        # NHL scorer credit defines each player point as one goal point or one
        # assist point. The point count/rate is derived, never independently fit.
        expected["points"] = expected["goals"] + expected["assists"]
        methods[method] = {
            "rate_per_60": {
                "goals": rates["goals"][method],
                "assists": rates["assists"][method],
                "points": rates["goals"][method] + rates["assists"][method],
            },
            "expected_count": expected,
            "probability_at_least_one": {
                stat: _poisson_probability_at_least_one(value)
                for stat, value in expected.items()
            },
        }
    return {
        "status": "research_projection",
        "games": len(prior),
        "projected_toi_minutes": projected_toi,
        "methods": methods,
        "last_event_gap": {
            event: _last_event_gap(prior, event, target_date)
            for event in ("goals", "assists", "points")
        },
        "last_event_gap_used_as_probability_adjustment": False,
        "points_identity": "expected_points = expected_goals + expected_assists",
        "probability_model": "independent Poisson goal and assist counts; exploratory",
        "validated": False,
    }


def _posterior_rate_weighted(rows, event, prior_rate, prior_minutes, decay):
    weighted_count = 0.0
    weighted_minutes = 0.0
    for index, row in enumerate(rows):
        weight = decay ** (len(rows) - index - 1)
        weighted_count += weight * row[event]
        weighted_minutes += weight * row["toi_minutes"]
    denominator = weighted_minutes + prior_minutes
    if denominator <= 0:
        return 0.0
    return 60.0 * (weighted_count + prior_rate * prior_minutes / 60.0) / denominator


def _binary_scores(probabilities, outcomes):
    if not probabilities:
        return {"n": 0, "brier": None, "log_loss": None,
                "observed_rate": None, "predicted_rate": None}
    eps = 1e-12
    n = len(probabilities)
    return {
        "n": n,
        "brier": sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / n,
        "log_loss": -sum(
            y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
            for p, y in zip(probabilities, outcomes)
        ) / n,
        "observed_rate": sum(outcomes) / n,
        "predicted_rate": sum(probabilities) / n,
    }


def _calibration_bins(probabilities, outcomes, groups=10):
    bins = []
    for index in range(groups):
        selected = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes)
            if min(groups - 1, int(probability * groups)) == index
        ]
        bins.append({
            "bin": index,
            "n": len(selected),
            "predicted": (sum(pair[0] for pair in selected) / len(selected)
                          if selected else None),
            "observed": (sum(pair[1] for pair in selected) / len(selected)
                         if selected else None),
        })
    return bins


def _summarize(records):
    report = {}
    for stat in ("goals", "assists", "points"):
        actual_count = [row["actual"][stat] for row in records]
        actual_binary = [int(value >= 1) for value in actual_count]
        report[stat] = {}
        for method in METHODS:
            expected = [row["prediction"]["methods"][method]["expected_count"][stat]
                        for row in records]
            probability = [row["prediction"]["methods"][method]
                           ["probability_at_least_one"][stat] for row in records]
            n = len(records)
            report[stat][method] = {
                "count_mae": (sum(abs(a - p) for a, p in zip(actual_count, expected)) / n
                              if n else None),
                "at_least_one": _binary_scores(probability, actual_binary),
                "calibration_bins": _calibration_bins(probability, actual_binary),
            }
    return report


def replay(rows, positions, start_date="2025-10-01"):
    """Walk forward by date; all players on a target date share prior-only rates."""
    by_date = defaultdict(list)
    for row in rows:
        by_date[row["date"]].append(row)
    player_history = defaultdict(list)
    peer_totals = defaultdict(lambda: {event: 0.0 for event in EVENTS} | {"minutes": 0.0})
    predictions = []
    for day in sorted(by_date):
        current = by_date[day]
        if day >= start_date:
            for row in current:
                pid = row["player_id"]
                position = positions.get(pid, "unknown")
                stats = peer_totals[position]
                peer_rates = {
                    position: {
                        event: 60.0 * stats[event] / stats["minutes"]
                        if stats["minutes"] else 0.0
                        for event in EVENTS
                    }
                }
                prediction = project(player_history[pid], row, position, peer_rates)
                if prediction["projection"] is not None:
                    predictions.append({
                        "game_id": row["game_id"], "date": day, "player_id": pid,
                        "team": row["team"], "position": position,
                        "prediction": prediction,
                        "actual": {event: row[event] for event in ("goals", "assists", "points")},
                    })
        # Update only after all targets on a date are forecast, preventing same-day leakage.
        for row in current:
            pid = row["player_id"]
            position = positions.get(pid, "unknown")
            player_history[pid].append(row)
            totals = peer_totals[position]
            totals["minutes"] += row["toi_minutes"]
            for event in EVENTS:
                totals[event] += row[event]
    return {
        "status": "research_only_not_calibrated",
        "observations": len(predictions),
        "players": len({row["player_id"] for row in predictions}),
        "scores": _summarize(predictions),
        "predictions": predictions,
        "limitations": [
            "Only total player TOI is currently modeled; per-game EV/PP/PK exposure is not in this log.",
            "RotoWire pregame PP units and injuries are not yet joined to this historical replay.",
            "Last-event gaps are reported for audit but not treated as an automatic hot/cold adjustment.",
            "Poisson probabilities and shrinkage prior exposure are research assumptions requiring walk-forward validation.",
        ],
    }


def run(teams, seasons=SEASONS, start_date="2025-10-01", fetch=None):
    from nhl.pulso_player_v3 import fetch_json
    rows, positions, sources = build(teams, seasons, fetch=fetch or fetch_json)
    rows = validate_gpa_rows(rows)
    result = replay(rows, positions, start_date)
    result["source_manifest"] = {
        "provider": "NHL Web API",
        "retrieved_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "teams": list(teams), "seasons": list(seasons),
        "raw_games": len(rows), "source_rows": sources,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default="EDM,COL,DAL,FLA,NYR,TOR")
    parser.add_argument("--seasons", default=",".join(SEASONS))
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    teams = TEAMS if args.teams == "ALL" else tuple(
        item.strip().upper() for item in args.teams.split(",")
    )
    if not teams or len(set(teams)) != len(teams) or any(team not in TEAMS for team in teams):
        raise ValueError("Invalid NHL team selection")
    seasons = tuple(args.seasons.split(","))
    if not seasons or any(season not in SEASONS for season in seasons):
        raise ValueError("Invalid NHL season selection")
    result = run(teams, seasons, args.start)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"observations": result["observations"],
                      "players": result["players"],
                      "status": result["status"]}))


if __name__ == "__main__":
    main()
