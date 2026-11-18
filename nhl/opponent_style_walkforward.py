"""Chronological, pregame-only evaluation of NHL opponent-style shot features.

This is a research challenger, not the production forecast. For a target date,
all games on that date are excluded from its features. Profiles must have
explicit event attribution and goal counts reconciled to official scores.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

FEATURE_VERSION = 1
WINDOWS = (5, 10, 20)
LOCATION_COEFFICIENTS = (0.0, 0.5, 1.0, 1.5)
PRIOR_STRENGTH_GAMES = 5
PRIOR_STRENGTH_SHOTS = 50
MIN_PRIOR_GAMES = 100
MIN_TUNE_GAMES = 100
MIN_HOLDOUT_GAMES = 100


def _valid_record(row):
    if row.get("opponent_style_features_version") != FEATURE_VERSION:
        return False, "missing_or_old_style_features"
    profile = row.get("opponent_style_profile")
    if not isinstance(profile, dict):
        return False, "missing_style_profile"
    result = row.get("result_final") or {}
    if type(result.get("home_goals")) is not int or type(result.get("away_goals")) is not int:
        return False, "missing_official_score"
    teams = profile.get("team_profiles") or {}
    if row.get("home") not in teams or row.get("away") not in teams:
        return False, "team_profile_missing"
    for team in (row["home"], row["away"]):
        check = (teams[team].get("goal_attribution_check") or {})
        if check.get("matches_scoreboard") is not True:
            return False, "goal_attribution_not_reconciled"
    return True, None


def load_archive(archive_dir):
    rows, excluded, seen = [], defaultdict(int), set()
    for path in sorted(Path(archive_dir).glob("*.json")):
        if path.name == "manifest.json":
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            excluded["invalid_json"] += 1
            continue
        valid, reason = _valid_record(row)
        if not valid:
            excluded[reason] += 1
            continue
        game_id = str(row.get("game_id", ""))
        if not game_id or game_id in seen:
            excluded["duplicate_or_missing_game_id"] += 1
            continue
        if not row.get("date") or not row.get("home") or not row.get("away"):
            excluded["missing_fixture_fields"] += 1
            continue
        seen.add(game_id)
        rows.append(row)
    rows.sort(key=lambda item: (item["date"], str(item["game_id"])))
    return rows, dict(sorted(excluded.items()))


def _team_game_record(game, team):
    profile = game["opponent_style_profile"]["team_profiles"][team]
    is_home = team == game["home"]
    result = game["result_final"]
    goals_for = result["home_goals"] if is_home else result["away_goals"]
    goals_against = result["away_goals"] if is_home else result["home_goals"]
    attack = profile["attack"]
    defense = profile["defense_allowed"]
    return {
        "date": game["date"],
        "goals_for": goals_for,
        "goals_against": goals_against,
        "attempts_for": int(attack.get("shot_events", 0)),
        "attempts_against": int(defense.get("shot_events", 0)),
        "located_for": int(attack.get("located_unblocked_shots", 0)),
        "located_against": int(defense.get("located_unblocked_shots", 0)),
        "near_for": int((attack.get("distance_bins_ft") or {}).get("0-25", 0)),
        "near_against": int((defense.get("distance_bins_ft") or {}).get("0-25", 0)),
    }


def _league_prior(games):
    attempts = goals = close = located = 0
    team_sides = 0
    for game in games:
        sides = game["opponent_style_profile"]["team_profiles"]
        for team in (game["home"], game["away"]):
            attack = sides[team]["attack"]
            result = game["result_final"]
            goals += result["home_goals"] if team == game["home"] else result["away_goals"]
            attempts += int(attack.get("shot_events", 0))
            located += int(attack.get("located_unblocked_shots", 0))
            close += int((attack.get("distance_bins_ft") or {}).get("0-25", 0))
            team_sides += 1
    if team_sides == 0:
        return {"goals_per_team_game": 3.0, "attempts_per_team_game": 30.0,
                "close_share": 0.35}
    return {
        "goals_per_team_game": goals / team_sides,
        "attempts_per_team_game": attempts / team_sides,
        "close_share": close / located if located else 0.35,
    }


def _smoothed_rate(total, n, prior, strength=PRIOR_STRENGTH_GAMES):
    return (total + strength * prior) / (n + strength)


def _team_rates(history, league, window):
    sample = history[-window:]
    n = len(sample)
    goals_for = _smoothed_rate(sum(r["goals_for"] for r in sample), n,
                               league["goals_per_team_game"])
    goals_against = _smoothed_rate(sum(r["goals_against"] for r in sample), n,
                                   league["goals_per_team_game"])
    attempts_for = _smoothed_rate(sum(r["attempts_for"] for r in sample), n,
                                  league["attempts_per_team_game"])
    attempts_against = _smoothed_rate(sum(r["attempts_against"] for r in sample), n,
                                      league["attempts_per_team_game"])
    located_for = sum(r["located_for"] for r in sample)
    located_against = sum(r["located_against"] for r in sample)
    close_for = ((sum(r["near_for"] for r in sample) +
                  PRIOR_STRENGTH_SHOTS * league["close_share"]) /
                 (located_for + PRIOR_STRENGTH_SHOTS))
    close_against = ((sum(r["near_against"] for r in sample) +
                      PRIOR_STRENGTH_SHOTS * league["close_share"]) /
                     (located_against + PRIOR_STRENGTH_SHOTS))
    base_goals = (goals_for + goals_against) / 2
    expected_attempts = (attempts_for + attempts_against) / 2
    league_attempts = max(league["attempts_per_team_game"], 1e-9)
    volume_ratio = min(1.3, max(0.7, expected_attempts / league_attempts))
    close_delta = (close_for + close_against) / 2 - league["close_share"]
    return {
        "base_goals": min(9.0, max(0.05, base_goals)),
        "volume_ratio": volume_ratio,
        "close_delta": close_delta,
        "history_games": n,
    }


def build_time_safe_features(games, window=10, min_prior_games=MIN_PRIOR_GAMES):
    """Build forecasts from games strictly earlier than each target calendar date."""
    ordered = sorted(games, key=lambda item: (item["date"], str(item["game_id"])))
    by_date = defaultdict(list)
    for game in ordered:
        by_date[game["date"]].append(game)
    team_history = defaultdict(list)
    prior_games = []
    output = []
    for day in sorted(by_date):
        league = _league_prior(prior_games)
        for game in by_date[day]:
            home_rates = _team_rates(team_history[game["home"]], league, window)
            away_rates = _team_rates(team_history[game["away"]], league, window)
            output.append({
                "date": day,
                "game_id": str(game["game_id"]),
                "home": game["home"],
                "away": game["away"],
                "actual_home_goals": game["result_final"]["home_goals"],
                "actual_away_goals": game["result_final"]["away_goals"],
                "actual_home_win": (
                    1.0 if game["result_final"]["home_goals"] >
                    game["result_final"]["away_goals"] else
                    0.0 if game["result_final"]["home_goals"] <
                    game["result_final"]["away_goals"] else 0.5
                ),
                "base_home_goals": home_rates["base_goals"],
                "base_away_goals": away_rates["base_goals"],
                "home_volume_ratio": home_rates["volume_ratio"],
                "away_volume_ratio": away_rates["volume_ratio"],
                "home_close_delta": home_rates["close_delta"],
                "away_close_delta": away_rates["close_delta"],
                "home_history_games": home_rates["history_games"],
                "away_history_games": away_rates["history_games"],
                "prior_game_count": len(prior_games),
                "eligible_for_evaluation": len(prior_games) >= min_prior_games,
            })
        # Conservative cutoff: no result from the target date enters any forecast
        # for another game on that same date.
        for game in by_date[day]:
            prior_games.append(game)
            team_history[game["home"]].append(_team_game_record(game, game["home"]))
            team_history[game["away"]].append(_team_game_record(game, game["away"]))
    return output


def _poisson_distribution(rate, max_goals=25):
    rate = min(9.0, max(0.05, rate))
    values = [math.exp(-rate)]
    for goals in range(1, max_goals + 1):
        values.append(values[-1] * rate / goals)
    total = sum(values)
    return [value / total for value in values]


def home_win_probability(home_rate, away_rate):
    home = _poisson_distribution(home_rate)
    away = _poisson_distribution(away_rate)
    return min(1.0, max(0.0, sum(
        p_home * (sum(away[:goals]) + 0.5 * away[goals])
        for goals, p_home in enumerate(home)
    )))


def _forecast(row, model, alpha=0.0):
    if model == "baseline":
        return row["base_home_goals"], row["base_away_goals"]
    home = row["base_home_goals"] * row["home_volume_ratio"] * math.exp(
        alpha * row["home_close_delta"])
    away = row["base_away_goals"] * row["away_volume_ratio"] * math.exp(
        alpha * row["away_close_delta"])
    return min(9.0, max(0.05, home)), min(9.0, max(0.05, away))


def metrics(rows, model="baseline", alpha=0.0):
    if not rows:
        raise ValueError("Cannot score an empty date window")
    absolute_error = squared_error = poisson_loss = 0.0
    brier = log_loss = 0.0
    for row in rows:
        home_rate, away_rate = _forecast(row, model, alpha)
        actuals = (row["actual_home_goals"], row["actual_away_goals"])
        for rate, observed in zip((home_rate, away_rate), actuals):
            absolute_error += abs(rate - observed)
            squared_error += (rate - observed) ** 2
            poisson_loss += rate - observed * math.log(rate) + math.lgamma(observed + 1)
        p_home = home_win_probability(home_rate, away_rate)
        actual_home_win = row["actual_home_win"]
        brier += (p_home - actual_home_win) ** 2
        if actual_home_win == 0.5:
            log_loss -= 0.5 * (math.log(max(1e-12, p_home)) +
                                math.log(max(1e-12, 1 - p_home)))
        else:
            observed_p = p_home if actual_home_win == 1.0 else 1 - p_home
            log_loss -= math.log(max(1e-12, observed_p))
    game_count = len(rows)
    side_count = 2 * game_count
    return {
        "games": game_count,
        "team_goal_mae": round(absolute_error / side_count, 6),
        "team_goal_rmse": round(math.sqrt(squared_error / side_count), 6),
        "team_goal_poisson_nll": round(poisson_loss / side_count, 6),
        "moneyline_brier": round(brier / game_count, 6),
        "moneyline_log_loss": round(log_loss / game_count, 6),
    }


def evaluate(games, excluded=None):
    if len(games) < 500:
        raise ValueError("At least 500 reconciled historical games are required")
    dates = sorted({game["date"] for game in games})
    if len(dates) < 30:
        raise ValueError("At least 30 distinct game dates are required")
    tune_start = dates[int(len(dates) * 0.60)]
    holdout_start = dates[int(len(dates) * 0.80)]
    results = {}
    for window in WINDOWS:
        timeline = build_time_safe_features(games, window=window)
        eligible = [row for row in timeline if row["eligible_for_evaluation"]]
        tune = [row for row in eligible if tune_start <= row["date"] < holdout_start]
        holdout = [row for row in eligible if row["date"] >= holdout_start]
        if len(tune) < MIN_TUNE_GAMES or len(holdout) < MIN_HOLDOUT_GAMES:
            continue
        for alpha in LOCATION_COEFFICIENTS:
            results[(window, alpha)] = {
                "tune": metrics(tune, "style", alpha),
                "holdout": metrics(holdout, "style", alpha),
                "tune_rows": tune,
                "holdout_rows": holdout,
            }
    if not results:
        raise ValueError("Insufficient chronological tune/holdout sample")
    best = min(results, key=lambda key: (
        results[key]["tune"]["team_goal_poisson_nll"], key[0], key[1]))
    selected = results[best]
    reference_timeline = build_time_safe_features(games, window=best[0])
    reference = [row for row in reference_timeline
                 if row["eligible_for_evaluation"] and row["date"] >= holdout_start]
    baseline_holdout = metrics(reference, "baseline")
    candidate_holdout = selected["holdout"]
    return {
        "kind": "nhl_opponent_style_chronological_evaluation_v1",
        "source_games": len(games),
        "excluded_records": excluded or {},
        "feature_window_games": best[0],
        "close_location_coefficient": best[1],
        "tuning_selection": "Minimum team-goal Poisson NLL on the tune window only.",
        "warmup_end_before": tune_start,
        "tune_window": {"from": tune_start, "through_exclusive": holdout_start,
                        "games": selected["tune"]["games"],
                        "candidate": selected["tune"]},
        "untouched_holdout": {"from": holdout_start,
                              "games": candidate_holdout["games"],
                              "baseline": baseline_holdout,
                              "candidate": candidate_holdout},
        "holdout_delta_candidate_minus_baseline": {
            metric: round(candidate_holdout[metric] - baseline_holdout[metric], 6)
            for metric in ("team_goal_mae", "team_goal_rmse", "team_goal_poisson_nll",
                           "moneyline_brier", "moneyline_log_loss")
        },
        "interpretation": {
            "improved_team_goal_poisson_nll": (
                candidate_holdout["team_goal_poisson_nll"] <
                baseline_holdout["team_goal_poisson_nll"]),
            "improved_moneyline_brier": (
                candidate_holdout["moneyline_brier"] < baseline_holdout["moneyline_brier"]),
            "eligible_for_production": False,
        },
        "controls": {
            "same_date_results_in_features": False,
            "target_game_pbp_in_features": False,
            "goal_events_reconciled_to_official_score": True,
            "postgame_rows_used_only_for_later_dates": True,
            "production_probabilities_changed": False,
            "automatic_promotion": False,
        },
        "model_definition": (
            "Baseline blends a team's prior goals-for with the opponent's prior goals-against, "
            "shrunk to the league rate. Challenger additionally multiplies by a capped prior "
            "shot-volume ratio and an exponentially scaled near-goal distance-share proxy."
        ),
        "limitations": [
            "Historical postgame PBP is converted into features only for strictly later dates; this is a retrospective research proxy, not a timestamped pregame capture.",
            "The holdout is chronological but remains within this historical archive; future-season prospective confirmation is still required.",
            "Distance-to-nearest-goal bands are geometric proxies, not NHL EDGE danger labels or a fitted expected-goals model.",
            "Independent Poisson scoring with a 50/50 split for ties is only an illustrative moneyline mapping; overtime and shootout dynamics are not modeled.",
            "No manpower-specific, on-ice matchup, line-chemistry, or goalie adjustment is included.",
            "A positive result is not enough to promote the feature; review sample coverage, uncertainty, and prospective performance first.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    games, excluded = load_archive(args.archive)
    report = evaluate(games, excluded)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_games": report["source_games"],
        "tune": report["tune_window"],
        "holdout": report["untouched_holdout"],
        "delta": report["holdout_delta_candidate_minus_baseline"],
        "controls": report["controls"],
    }, indent=2))


if __name__ == "__main__":
    main()
