"""Walk-forward challenger for NBA absence-conditioned production scenarios.

Fits one regularized log-odds coefficient from prior seasons only. It compares
against the frozen statistical baseline on later seasons and never promotes or
writes into the published forecast. Input scenarios must already be built from
verified point-in-time injury, minutes, and player production evidence.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MODEL_VERSION = "nba_availability_walk_forward_v1"
FEATURE_UNIT_POINTS_PER_GAME = 10.0
DEFAULT_PENALTY = 1.0


def moment(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("UTC timestamp required")
    return parsed


def logit(probability):
    if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 < probability < 1:
        raise ValueError("Probability must be finite and strictly between zero and one")
    return math.log(probability / (1 - probability))


def sigmoid(value):
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def validate(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Nonempty availability scenario ledger required")
    seen = set()
    clean = []
    for row in records:
        gid = str(row["game_id"])
        if not gid or gid in seen:
            raise ValueError("Game IDs must be nonempty and unique")
        seen.add(gid)
        tip = moment(row["tipoff_utc"])
        freeze = moment(row["prediction_as_of_utc"])
        feature = moment(row["feature_observed_at_utc"])
        if not feature <= freeze < tip:
            raise ValueError("Availability feature must be observed by the frozen prediction and before tipoff")
        if row.get("features_point_in_time_verified") is not True:
            raise ValueError("Unverified availability features cannot enter the ledger")
        if row.get("both_team_scenarios_complete") is not True:
            raise ValueError("Both teams need a complete absence/minute-redistribution scenario")
        if not row.get("source_snapshot_sha256") or not row.get("scenario_sha256"):
            raise ValueError("Snapshot and scenario hashes are required")
        season = row["season_end_year"]
        if type(season) is not int or season < 2000:
            raise ValueError("Invalid season_end_year")
        target = row["home_won"]
        if type(target) is not int or target not in (0, 1):
            raise ValueError("home_won must be 0 or 1")
        base = row["baseline_p_home"]
        logit(base)
        # This difference is derived from historical player output lost by OUT
        # players plus output gained by minute recipients. Its coefficient is
        # learned only on earlier seasons; no hand-set player-to-win weight.
        for field in ("home_net_output_change_per_game", "away_net_output_change_per_game"):
            value = row[field]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Net output change must be finite for both teams")
        if not row.get("baseline_model_version"):
            raise ValueError("Baseline model version is required")
        clean.append(dict(row))
    return sorted(clean, key=lambda r: (moment(r["tipoff_utc"]), str(r["game_id"])))


def feature(row):
    net_home_edge = (row["home_net_output_change_per_game"] - row["away_net_output_change_per_game"])
    return net_home_edge / FEATURE_UNIT_POINTS_PER_GAME


def fit_beta(training, penalty=DEFAULT_PENALTY, max_iterations=100, tolerance=1e-10):
    """Fit injury-only slope as an offset logistic model over baseline log-odds."""
    if len(training) < 2:
        raise ValueError("At least two training games required")
    if type(penalty) not in (int, float) or not math.isfinite(penalty) or penalty <= 0:
        raise ValueError("Positive finite ridge penalty required")
    beta = 0.0
    for _ in range(max_iterations):
        gradient = penalty * beta
        hessian = penalty
        for row in training:
            x = feature(row)
            p = sigmoid(logit(row["baseline_p_home"]) + beta * x)
            gradient += x * (p - row["home_won"])
            hessian += x * x * p * (1 - p)
        step = gradient / hessian
        beta -= step
        if not math.isfinite(beta):
            raise ValueError("Nonfinite fitted availability coefficient")
        if abs(step) < tolerance:
            return beta
    raise ValueError("Availability logistic fit did not converge")


def score(rows, probability_key):
    n = len(rows)
    if not n:
        return {"n": 0, "brier": None, "log_loss": None, "accuracy": None, "mean_probability": None}
    brier = loss = correct = 0.0
    probabilities = []
    for row in rows:
        p = row[probability_key]
        y = row["home_won"]
        brier += (p - y) ** 2
        loss -= y * math.log(max(1e-15, p)) + (1-y) * math.log(max(1e-15, 1-p))
        correct += int((p >= .5) == bool(y))
        probabilities.append(p)
    return {"n": n, "brier": brier/n, "log_loss": loss/n,
            "accuracy": correct/n, "mean_probability": sum(probabilities)/n}


def evaluate(records, min_train=100, min_holdout=100, penalty=DEFAULT_PENALTY):
    rows = validate(records)
    by_season = defaultdict(list)
    for row in rows:
        by_season[row["season_end_year"]].append(row)
    seasons = sorted(by_season)
    evaluations = []
    skipped = []
    predictions = []
    for season in seasons:
        training = [r for r in rows if r["season_end_year"] < season]
        holdout = by_season[season]
        if len(training) < min_train:
            skipped.append({"season_end_year": season, "reason": "insufficient_prior_season_training_games",
                            "training_games": len(training), "required": min_train})
            continue
        if len(holdout) < min_holdout:
            skipped.append({"season_end_year": season, "reason": "insufficient_holdout_games",
                            "holdout_games": len(holdout), "required": min_holdout})
            continue
        # Ensure every model-fitting outcome was final before the earliest
        # prediction freeze in this holdout season.
        cutoff = min(moment(r["prediction_as_of_utc"]) for r in holdout)
        if any(moment(r["tipoff_utc"]) >= cutoff for r in training):
            raise ValueError("Training outcome is not strictly prior to holdout prediction cutoff")
        beta = fit_beta(training, penalty=penalty)
        scored = []
        for row in holdout:
            candidate = sigmoid(logit(row["baseline_p_home"]) + beta * feature(row))
            scored.append({**row, "availability_candidate_p_home": candidate})
        base = score(scored, "baseline_p_home")
        candidate = score(scored, "availability_candidate_p_home")
        evaluations.append({"season_end_year": season, "training_games": len(training),
                            "holdout_games": len(holdout), "training_cutoff_utc": cutoff.isoformat(),
                            "training_dataset_sha256": hashlib.sha256(json.dumps(
                                [{"game_id": r["game_id"], "target": r["home_won"],
                                 "x": feature(r), "baseline": r["baseline_p_home"]}
                                 for r in training], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                            "coefficient_log_odds_per_10_net_points_per_game": beta,
                            "baseline": base, "availability_candidate": candidate,
                            "brier_gain": base["brier"] - candidate["brier"],
                            "log_loss_gain": base["log_loss"] - candidate["log_loss"]})
        predictions.extend({"game_id": r["game_id"], "season_end_year": season,
                            "baseline_p_home": r["baseline_p_home"],
                            "availability_candidate_p_home": r["availability_candidate_p_home"],
                            "home_won": r["home_won"], "feature_net_home_edge_per_10_points": feature(r),
                            "model_version": MODEL_VERSION} for r in scored)
    return {"schema_version": 1, "model": MODEL_VERSION,
            "input_ledger_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "feature": "home_minus_away(net historical output change after OUT removal and minute redistribution), per 10 points/game",
            "fit_method": "ridge logistic slope with frozen baseline log-odds offset; fitted on earlier seasons only",
            "ridge_penalty": penalty, "evaluated_seasons": evaluations, "skipped_seasons": skipped,
            "predictions": predictions,
            "improved_every_holdout": bool(evaluations) and all(
                item["brier_gain"] > 0 and item["log_loss_gain"] > 0 for item in evaluations),
            "independent_validation_passed": False, "automatic_promotion_allowed": False,
            "production_probabilities_changed": False,
            "limitations": ["Requires a source-backed historical availability ledger; current-season captures alone may be too small.",
                            "Historical point production and redistributed minutes are proxies, not causal player value.",
                            "Holdout improvement is a research result, not calibration certification or approval to change published probabilities."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Frozen JSON list of verified game-level baseline/scenario/outcome rows")
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-train", type=int, default=100)
    parser.add_argument("--min-holdout", type=int, default=100)
    parser.add_argument("--penalty", type=float, default=DEFAULT_PENALTY)
    args = parser.parse_args()
    if args.min_train < 2 or args.min_holdout < 1:
        parser.error("min-train must be >=2 and min-holdout >=1")
    result = evaluate(json.loads(Path(args.input).read_text()), args.min_train, args.min_holdout, args.penalty)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as output:
        json.dump(result, output, indent=2, sort_keys=True)
    print(json.dumps({"evaluated_seasons": [x["season_end_year"] for x in result["evaluated_seasons"]],
                      "skipped_seasons": result["skipped_seasons"],
                      "improved_every_holdout": result["improved_every_holdout"],
                      "independent_validation_passed": False,
                      "production_probabilities_changed": False}, indent=2))


if __name__ == "__main__":
    main()
