"""Chronological research estimate of NBA fatigue, rest and travel effects.

The candidate includes rest/B2B, venue sequence, recent game load, travel
distance, time-zone direction and body-clock tipoff hour. It is fitted against
pregame Challenger probabilities and only applied if both Brier and log loss
improve on a later chronological holdout. No odds or post-tip data are used.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from challenger import predict_challenger
from travel_context import game_context

MIN_TRAIN = 500
MIN_HOLDOUT = 100
HOLDOUT_FRACTION = 0.2
RIDGE = 10.0
MAX_LOG_ODDS_DELTA = 0.2


def utc(value):
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None or moment.utcoffset() != timezone.utc.utcoffset(moment):
        raise ValueError("Explicit UTC timestamp required")
    return moment.astimezone(timezone.utc)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


FEATURE_KEYS = (
    "distance_imbalance_1000km",
    "timezone_shift_imbalance_hours",
    "cumulative_travel_imbalance_1000km",
    "cumulative_timezone_shift_imbalance_hours",
    "cumulative_absolute_timezone_imbalance_hours",
    "body_clock_sin_imbalance",
    "body_clock_cos_imbalance",
    "distance_body_clock_sin_interaction",
    "distance_body_clock_cos_interaction",
    "back_to_back_imbalance",
    "rested_vs_back_to_back_imbalance",
    "games_last_4_days_imbalance",
    "games_last_7_days_imbalance",
    "home_b2b_after_home",
    "home_b2b_after_road",
    "away_b2b_after_home",
    "away_b2b_after_road",
)


def _travel_rows(rows):
    """Return pregame fatigue/travel features from strictly prior games."""
    features = []
    seen = []
    active_season = object()
    ordered = sorted(rows, key=lambda x: (utc(x["tipoff_utc"]), str(x["game_id"])))
    for row in ordered:
        season = row.get("season")
        if season != active_season:
            seen = []
            active_season = season
        teams = game_context(row["home_team"], row["away_team"], row["tipoff_utc"], seen)
        home = teams.get(row["home_team"], {})
        away = teams.get(row["away_team"], {})
        required = (
            home.get("travel_distance_km"), away.get("travel_distance_km"),
            home.get("timezone_shift_hours"), away.get("timezone_shift_hours"),
            home.get("body_clock_tipoff_hour"), away.get("body_clock_tipoff_hour"),
        )
        if all(type(value) in (int, float) and math.isfinite(value) for value in required):
            home_b2b = home.get("is_back_to_back") is True
            away_b2b = away.get("is_back_to_back") is True
            home_rest = home.get("rest_days")
            away_rest = away.get("rest_days")
            home_rest = home_rest if type(home_rest) is int else 0
            away_rest = away_rest if type(away_rest) is int else 0
            home_hour = math.tau * home["body_clock_tipoff_hour"] / 24.0
            away_hour = math.tau * away["body_clock_tipoff_hour"] / 24.0
            home_sin, away_sin = math.sin(home_hour), math.sin(away_hour)
            home_cos, away_cos = math.cos(home_hour), math.cos(away_hour)
            distance_imbalance = (away["travel_distance_km"] - home["travel_distance_km"]) / 1000.0
            body_sin_imbalance = away_sin - home_sin
            body_cos_imbalance = away_cos - home_cos
            home_path = home.get("back_to_back_path")
            away_path = away.get("back_to_back_path")
            features.append({
                "game_id": str(row["game_id"]),
                "tipoff_utc": row["tipoff_utc"],
                "distance_imbalance_1000km": distance_imbalance,
                "timezone_shift_imbalance_hours": away["timezone_shift_hours"] - home["timezone_shift_hours"],
                "cumulative_travel_imbalance_1000km": (
                    away.get("cumulative_travel_km_last_7_days", 0) -
                    home.get("cumulative_travel_km_last_7_days", 0)) / 1000.0,
                "cumulative_timezone_shift_imbalance_hours": (
                    away.get("cumulative_timezone_shift_hours_last_7_days", 0) -
                    home.get("cumulative_timezone_shift_hours_last_7_days", 0)),
                "cumulative_absolute_timezone_imbalance_hours": (
                    away.get("cumulative_absolute_timezone_shift_hours_last_7_days", 0) -
                    home.get("cumulative_absolute_timezone_shift_hours_last_7_days", 0)),
                "body_clock_sin_imbalance": body_sin_imbalance,
                "body_clock_cos_imbalance": body_cos_imbalance,
                "distance_body_clock_sin_interaction": distance_imbalance * body_sin_imbalance,
                "distance_body_clock_cos_interaction": distance_imbalance * body_cos_imbalance,
                "back_to_back_imbalance": int(away_b2b) - int(home_b2b),
                "rested_vs_back_to_back_imbalance": (
                    int(away_b2b and home_rest >= 1) - int(home_b2b and away_rest >= 1)),
                "games_last_4_days_imbalance": away.get("games_last_4_days", 0) - home.get("games_last_4_days", 0),
                "games_last_7_days_imbalance": away.get("games_last_7_days", 0) - home.get("games_last_7_days", 0),
                "home_b2b_after_home": int(home_b2b and home_path == "home_to_home"),
                "home_b2b_after_road": int(home_b2b and home_path == "road_to_home"),
                "away_b2b_after_home": int(away_b2b and away_path == "home_to_road"),
                "away_b2b_after_road": int(away_b2b and away_path == "road_to_road"),
            })
        seen.append(row)
    return features


def _sigmoid(x):
    x = max(-30.0, min(30.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p):
    p = min(1.0 - 1e-9, max(1e-9, p))
    return math.log(p / (1.0 - p))


def _solve(matrix, vector):
    """Solve a small positive-definite Newton system with pivoting."""
    n = len(vector)
    a = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("Singular travel coefficient fit")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [value / scale for value in a[col]]
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor:
                a[row] = [left - factor * right for left, right in zip(a[row], a[col])]
    return [a[i][-1] for i in range(n)]


def _fit(samples):
    dimensions = len(samples[0][0])
    means = [sum(row[0][j] for row in samples) / len(samples) for j in range(dimensions)]
    scales = [math.sqrt(sum((row[0][j] - means[j]) ** 2 for row in samples) / len(samples))
              for j in range(dimensions)]
    scales = [scale if scale > 1e-8 else 1.0 for scale in scales]
    xs = [[(row[0][j] - means[j]) / scales[j] for j in range(dimensions)] for row in samples]
    beta = [0.0] * dimensions
    for _ in range(80):
        gradient = [-RIDGE * value for value in beta]
        hessian = [[0.0] * dimensions for _ in range(dimensions)]
        for j in range(dimensions):
            hessian[j][j] = RIDGE
        for x, (offset, outcome) in zip(xs, (row[1] for row in samples)):
            p = _sigmoid(offset + sum(coef * value for coef, value in zip(beta, x)))
            weight = max(1e-8, p * (1.0 - p))
            error = outcome - p
            for j in range(dimensions):
                gradient[j] += error * x[j]
                for k in range(dimensions):
                    hessian[j][k] += weight * x[j] * x[k]
        step = _solve(hessian, gradient)
        beta = [max(-2.0, min(2.0, beta[j] + step[j])) for j in range(dimensions)]
        if max(abs(value) for value in step) < 1e-7:
            break
    return {"coefficients_standardized": beta, "feature_means": means, "feature_scales": scales}


def _metrics(samples, model):
    brier = base_ll = adjusted_ll = adjusted_brier = 0.0
    for x, (offset, outcome) in zip(model["holdout_x"], samples):
        base = _sigmoid(offset)
        adjusted = _sigmoid(offset + sum(a * b for a, b in zip(model["fit"]["coefficients_standardized"], x)))
        brier += (base - outcome) ** 2
        adjusted_brier += (adjusted - outcome) ** 2
        base_ll -= outcome * math.log(max(base, 1e-12)) + (1-outcome) * math.log(max(1-base, 1e-12))
        adjusted_ll -= outcome * math.log(max(adjusted, 1e-12)) + (1-outcome) * math.log(max(1-adjusted, 1e-12))
    n = len(samples)
    return {"games": n, "baseline_brier": brier/n, "travel_brier": adjusted_brier/n,
            "baseline_log_loss": base_ll/n, "travel_log_loss": adjusted_ll/n}


def _sample(history, cutoff):
    rows = []
    for row in history if isinstance(history, list) else history.get("games", []):
        try:
            if utc(row["tipoff_utc"]) >= cutoff:
                continue
            home, away = row["home_points"], row["away_points"]
            if type(home) not in (int, float) or type(away) not in (int, float):
                continue
            if not math.isfinite(home) or not math.isfinite(away):
                continue
            rows.append(dict(row))
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: (utc(x["tipoff_utc"]), str(x["game_id"])))
    if not rows:
        return []
    features = {row["game_id"]: row for row in _travel_rows(rows)}
    challenger = predict_challenger(rows)
    predictions = {str(row["game_id"]): pred for row, pred in zip(rows, challenger)}
    samples = []
    for row in rows:
        feature = features.get(str(row["game_id"]))
        pred = predictions.get(str(row["game_id"]))
        if feature is None or pred is None:
            continue
        samples.append((feature, (_logit(pred["p_home"]), int(row["home_points"] > row["away_points"]))))
    return samples


def _apply_fit(sample_rows):
    cut = int(len(sample_rows) * (1.0 - HOLDOUT_FRACTION))
    train, holdout = sample_rows[:cut], sample_rows[cut:]
    if len(train) < MIN_TRAIN or len(holdout) < MIN_HOLDOUT:
        return {"status": "insufficient_chronological_sample", "train_games": len(train),
                "holdout_games": len(holdout), "applied": False}
    fit = _fit([([x[key] for key in FEATURE_KEYS], y) for x, y in train])
    standardized = [[(x[key]-fit["feature_means"][j])/fit["feature_scales"][j]
                     for j, key in enumerate(FEATURE_KEYS)] for x, _ in holdout]
    metrics = _metrics([y for _, y in holdout], {"fit": fit, "holdout_x": standardized})
    passed = (metrics["travel_brier"] < metrics["baseline_brier"]
              and metrics["travel_log_loss"] < metrics["baseline_log_loss"])
    if not passed:
        return {"status": "holdout_no_improvement", "train_games": len(train),
                "holdout": metrics, "applied": False}
    full_fit = _fit([([x[key] for key in FEATURE_KEYS], y) for x, y in sample_rows])
    return {"status": "research_adjustment_validated_on_chronological_holdout",
            "train_games": len(train), "holdout": metrics, "fit": full_fit,
            "applied": True}


def build(snapshot, module_context, history):
    snapshot_body = {k: v for k, v in snapshot.items() if k != "content_sha256"}
    if digest(snapshot_body) != snapshot.get("content_sha256"):
        raise ValueError("Snapshot digest mismatch")
    if module_context.get("snapshot_sha256") != snapshot.get("content_sha256"):
        raise ValueError("Travel module context does not match snapshot")
    context_body = {k: v for k, v in module_context.items() if k != "content_sha256"}
    if digest(context_body) != module_context.get("content_sha256"):
        raise ValueError("Module context digest mismatch")
    emitted = utc(snapshot["created_at_utc"])
    sample_rows = _sample(history, emitted)
    fitted = _apply_fit(sample_rows)
    rows = history if isinstance(history, list) else history.get("games", [])
    historical = []
    for row in rows:
        try:
            if utc(row["tipoff_utc"]) < emitted and row.get("home_points") is not None and row.get("away_points") is not None:
                historical.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    future = [{"game_id": p["game_id"], "tipoff_utc": p["tipoff_utc"],
               "home_team": p["home_team"], "away_team": p["away_team"]}
              for p in snapshot.get("predictions", [])]
    feature_map = {x["game_id"]: x for x in _travel_rows([*historical, *future])}
    result = []
    for fixture in snapshot.get("predictions", []):
        gid = str(fixture["game_id"]); feature = feature_map.get(gid)
        base = fixture["hybrid_p_home"]
        row = {"game_id": gid, "status": fitted["status"], "base_home_probability": base,
               "travel_adjusted_home_probability": None, "log_odds_delta": 0.0,
               "feature": feature, "holdout": fitted.get("holdout"),
               "train_games": fitted.get("train_games", 0), "applied": False,
               "calibrated": False, "production_approved": False}
        if fitted.get("applied") and feature is not None:
            fit = fitted["fit"]
            z = [(feature[key]-fit["feature_means"][i])/fit["feature_scales"][i]
                 for i, key in enumerate(FEATURE_KEYS)]
            delta = sum(a*b for a, b in zip(fit["coefficients_standardized"], z))
            delta = max(-MAX_LOG_ODDS_DELTA, min(MAX_LOG_ODDS_DELTA, delta))
            adjusted = _sigmoid(_logit(base)+delta)
            row.update({"status": "research_scenario", "log_odds_delta": delta,
                        "travel_adjusted_home_probability": adjusted,
                        "applied": not math.isclose(adjusted, base, rel_tol=0, abs_tol=1e-12)})
        result.append(row)
    body = {"schema_version": 1, "snapshot_sha256": snapshot["content_sha256"],
            "created_at_utc": snapshot["created_at_utc"], "games": result,
            "validation": fitted, "calibrated": False, "production_approved": False,
            "no_odds_input": True}
    body["content_sha256"] = digest(body)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "module-context", "history", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    result = build(read(args.snapshot), read(args.module_context), read(args.history))
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        json.dump(result, output, indent=2, allow_nan=False)
    print(json.dumps({"games": len(result["games"]), "status": result["validation"]["status"],
                      "applied_games": sum(row["applied"] for row in result["games"])}))


if __name__ == "__main__":
    main()
