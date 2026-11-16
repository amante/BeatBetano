"""Prospective NBA team confidence diagnostic across frozen snapshots.

Descriptive only: pairs pregame forecasts with settled results, reports sample
sizes by team and model revision, and never fits or changes probabilities.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


MODEL_FIELDS = {
    "elo": "elo_p_home",
    "challenger": "challenger_p_home",
    "hybrid": "hybrid_p_home",
}


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_snapshot(snapshot):
    expected = snapshot.get("content_sha256")
    body = {key: value for key, value in snapshot.items() if key != "content_sha256"}
    if not isinstance(expected, str) or digest(body) != expected:
        raise ValueError("Frozen snapshot digest mismatch")


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("Explicit UTC timestamp required")
    return parsed


def _probability(row, field, home):
    value = row.get(field)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1:
        return None
    return float(value) if home else 1.0 - float(value)


def _metric(pairs):
    if not pairs:
        return {"n": 0, "mean_forecast": None, "observed_win_rate": None,
                "mean_bias": None, "brier": None, "log_loss": None, "accuracy": None}
    n = len(pairs)
    return {
        "n": n,
        "mean_forecast": sum(p for p, _ in pairs) / n,
        "observed_win_rate": sum(y for _, y in pairs) / n,
        "mean_bias": sum(p - y for p, y in pairs) / n,
        "brier": sum((p - y) ** 2 for p, y in pairs) / n,
        "log_loss": -sum(y * math.log(p) + (1 - y) * math.log1p(-p) for p, y in pairs) / n,
        "accuracy": sum((p >= 0.5) == bool(y) for p, y in pairs) / n,
    }


def _outcomes(history, settled):
    result = {}
    for row in history if isinstance(history, list) else history.get("games", []):
        game_id = str(row.get("id", row.get("game_id", "")))
        completed = row.get("completed") is True
        try:
            home_score = float(row.get("home_score", row.get("home_points")))
            away_score = float(row.get("away_score", row.get("away_points")))
        except (TypeError, ValueError):
            continue
        if game_id and completed and math.isfinite(home_score) and math.isfinite(away_score):
            result[game_id] = int(home_score > away_score)
    if isinstance(settled, dict):
        for row in settled.get("games", []):
            game_id = str(row.get("game_id", ""))
            outcome = row.get("outcome_home")
            if game_id and type(outcome) is int and outcome in (0, 1):
                result[game_id] = outcome
    return result


def collect(prediction_dir, history, settled=None):
    outcomes = _outcomes(history, settled)
    chosen = {}
    skipped_after_tipoff = 0
    snapshots = []
    for path in sorted(Path(prediction_dir).glob("run-*.json")):
        snapshot = json.loads(path.read_text())
        verify_snapshot(snapshot)
        issued = utc(snapshot["created_at_utc"])
        provenance = snapshot.get("model_provenance") or {}
        revision = str(provenance.get("model_code_revision") or "unknown_revision")
        snapshots.append({"file": path.name, "snapshot_sha256": snapshot["content_sha256"],
                          "created_at_utc": snapshot["created_at_utc"], "model_revision": revision})
        seen = set()
        for row in snapshot.get("predictions", []):
            game_id = str(row.get("game_id", ""))
            if not game_id or game_id in seen:
                raise ValueError("Missing or duplicate game ID in frozen snapshot")
            seen.add(game_id)
            tipoff = utc(row["tipoff_utc"])
            if issued >= tipoff:
                skipped_after_tipoff += 1
                continue
            if game_id not in outcomes:
                continue
            candidate = {
                "game_id": game_id,
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "tipoff_utc": row["tipoff_utc"],
                "prediction_as_of_utc": snapshot["created_at_utc"],
                "model_revision": revision,
                "snapshot_file": path.name,
                "snapshot_sha256": snapshot["content_sha256"],
                "outcome_home": outcomes[game_id],
                "probabilities_home": {
                    model: row.get(field) for model, field in MODEL_FIELDS.items()
                },
            }
            previous = chosen.get(game_id)
            if previous is None or issued > utc(previous["prediction_as_of_utc"]):
                chosen[game_id] = candidate
            elif issued == utc(previous["prediction_as_of_utc"]) and candidate != previous:
                raise ValueError("Conflicting frozen predictions have the same issue time")
    return list(chosen.values()), snapshots, skipped_after_tipoff


def _model_metrics(rows, home=True):
    pairs = []
    for row in rows:
        p = row["probabilities_home"].get("hybrid")
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
            continue
        pairs.append((float(p) if home else 1.0 - float(p),
                      row["outcome_home"] if home else 1 - row["outcome_home"]))
    return _metric(pairs)


def build(prediction_dir, history, settled=None):
    rows, snapshots, skipped_after_tipoff = collect(prediction_dir, history, settled)
    models = {}
    for model in MODEL_FIELDS:
        pairs = []
        for row in rows:
            raw = row["probabilities_home"].get(model)
            if type(raw) not in (int, float) or not math.isfinite(raw) or not 0 < raw < 1:
                continue
            pairs.append((float(raw), row["outcome_home"]))
        models[model] = _metric(pairs)

    teams = {}
    for row in rows:
        for side, team in (("home", row["home_team"]), ("away", row["away_team"])):
            record = teams.setdefault(team, {"games": 0, "home_games": 0, "away_games": 0,
                                             "models": {name: [] for name in MODEL_FIELDS}})
            record["games"] += 1
            record[side + "_games"] += 1
            for model, field in MODEL_FIELDS.items():
                probability = _probability(row["probabilities_home"], field, side == "home")
                if probability is not None:
                    outcome = row["outcome_home"] if side == "home" else 1 - row["outcome_home"]
                    record["models"][model].append((probability, outcome))
    team_report = {}
    for team, record in sorted(teams.items()):
        team_report[team] = {
            "games": record["games"],
            "home_games": record["home_games"],
            "away_games": record["away_games"],
            "models": {name: _metric(pairs) for name, pairs in record["models"].items()},
        }
    minnesota = team_report.get("MIN", {
        "games": 0, "home_games": 0, "away_games": 0,
        "models": {name: _metric([]) for name in MODEL_FIELDS},
    })
    if minnesota["games"] == 1:
        minnesota_conclusion = "single_observation_no_reliability_conclusion"
    elif minnesota["games"] == 0:
        minnesota_conclusion = "no_settled_minnesota_predictions"
    else:
        minnesota_conclusion = "descriptive_cohort_only_no_parameter_changes"
    return {
        "schema_version": 1,
        "kind": "nba_team_confidence_diagnostic_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scored_games": len(rows),
        "deduplicated_to_latest_pregame_forecast_per_game": True,
        "skipped_post_tipoff_predictions": skipped_after_tipoff,
        "models": models,
        "team_metrics": team_report,
        "minnesota_diagnostic": {
            **minnesota,
            "conclusion": minnesota_conclusion,
            "coefficients_changed": False,
            "promotion_allowed": False,
        },
        "paired_games": rows,
        "source_snapshots": snapshots,
        "limitations": [
            "This report is a prospective but small and non-independent monitoring sample.",
            "Snapshots may contain different model code revisions; revisions are disclosed and not treated as one certified model.",
            "Team-level win rates do not identify a cause of forecast error.",
            "No calibration, coefficients, or production route are changed by this diagnostic.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-dir", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--settled")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    history = json.loads(Path(args.history).read_text())
    settled = json.loads(Path(args.settled).read_text()) if args.settled else None
    report = build(args.prediction_dir, history, settled)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({
        "scored_games": report["scored_games"],
        "minnesota_games": report["minnesota_diagnostic"]["games"],
        "minnesota_conclusion": report["minnesota_diagnostic"]["conclusion"],
        "coefficients_changed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
