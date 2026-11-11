"""Chronological research estimate of NBA travel's incremental win effect.

The feature is fitted against pregame challenger probabilities on earlier
games, then must improve both Brier score and log loss on a later holdout.
It is never used when the point-in-time sample is too small or validation
does not pass. No odds or post-tip information is consumed.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger import predict_challenger
from team_identity import canonical
from travel_context import VENUES, distance_km

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


def _travel_rows(rows):
    """Return pregame travel features, updating each team's venue after games."""
    last_venue = {}
    features = []
    for row in sorted(rows, key=lambda x: (utc(x["tipoff_utc"]), str(x["game_id"]))):
        home, away = canonical(row["home_team"]), canonical(row["away_team"])
        destination = VENUES.get(home)
        current = {}
        for team in (home, away):
            origin = last_venue.get(team)
            if destination is None or origin is None or origin not in VENUES:
                current[team] = None
                continue
            origin_info = VENUES[origin]
            distance = distance_km(origin_info, destination)
            when = utc(row["tipoff_utc"])
            origin_offset = when.astimezone(ZoneInfo(origin_info[2])).utcoffset()
            destination_offset = when.astimezone(ZoneInfo(destination[2])).utcoffset()
            shift = (destination_offset - origin_offset).total_seconds() / 3600
            current[team] = (distance, shift)
        if current.get(home) is not None and current.get(away) is not None:
            features.append({
                "game_id": str(row["game_id"]),
                "tipoff_utc": row["tipoff_utc"],
                "distance_imbalance_1000km": (current[away][0] - current[home][0]) / 1000.0,
                "timezone_shift_imbalance_hours": current[away][1] - current[home][1],
            })
        # A team's previous venue is its home arena when home, otherwise its
        # opponent's arena. This also handles consecutive away games correctly.
        last_venue[home] = home
        last_venue[away] = home
    return features


def _sigmoid(x):
    x = max(-30.0, min(30.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p):
    p = min(1.0 - 1e-9, max(1e-9, p))
    return math.log(p / (1.0 - p))


def _fit(samples):
    means = [sum(row[0][j] for row in samples) / len(samples) for j in range(2)]
    scales = [math.sqrt(sum((row[0][j] - means[j]) ** 2 for row in samples) / len(samples)) for j in range(2)]
    scales = [s if s > 1e-8 else 1.0 for s in scales]
    xs = [[(row[0][j] - means[j]) / scales[j] for j in range(2)] for row in samples]
    beta = [0.0, 0.0]
    for _ in range(60):
        g = [-RIDGE * beta[0], -RIDGE * beta[1]]
        h00 = h11 = RIDGE
        h01 = 0.0
        for x, (offset, outcome) in zip(xs, (row[1] for row in samples)):
            p = _sigmoid(offset + beta[0] * x[0] + beta[1] * x[1])
            weight = max(1e-8, p * (1.0 - p))
            error = outcome - p
            g[0] += error * x[0]; g[1] += error * x[1]
            h00 += weight * x[0] * x[0]
            h11 += weight * x[1] * x[1]
            h01 += weight * x[0] * x[1]
        det = h00 * h11 - h01 * h01
        if det <= 1e-12:
            raise ValueError("Singular travel coefficient fit")
        step = [(g[0] * h11 - g[1] * h01) / det,
                (g[1] * h00 - g[0] * h01) / det]
        beta = [max(-2.0, min(2.0, beta[i] + step[i])) for i in range(2)]
        if max(abs(step[0]), abs(step[1])) < 1e-7:
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
    fit = _fit([([x["distance_imbalance_1000km"], x["timezone_shift_imbalance_hours"]], y)
                for x, y in train])
    keys = ("distance_imbalance_1000km", "timezone_shift_imbalance_hours")
    standardized = [[(x[keys[j]]-fit["feature_means"][j])/fit["feature_scales"][j] for j in range(2)] for x, _ in holdout]
    metrics = _metrics([y for _, y in holdout], {"fit": fit, "holdout_x": standardized})
    passed = (metrics["travel_brier"] < metrics["baseline_brier"]
              and metrics["travel_log_loss"] < metrics["baseline_log_loss"])
    if not passed:
        return {"status": "holdout_no_improvement", "train_games": len(train),
                "holdout": metrics, "applied": False}
    full_fit = _fit([([x["distance_imbalance_1000km"], x["timezone_shift_imbalance_hours"]], y)
                     for x, y in sample_rows])
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
                 for i, key in enumerate(("distance_imbalance_1000km", "timezone_shift_imbalance_hours"))]
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
