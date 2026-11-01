"""#263: audit the actual historical training evidence required for goalie-conditioned ML.

Existing outcome-only labels have no starter IDs or pregame goalie features.
Never train on current-day candidate SV% or silently join postgame starter data.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

FEATURES = ("home_goalie_prior_sv", "away_goalie_prior_sv",
            "home_team_prior_strength", "away_team_prior_strength")
REQUIRED = ("game_id", "date", "home", "away", "home_goalie_id",
            "away_goalie_id", "ml_winner", "feature_as_of_date") + FEATURES

def audit(rows, minimum_train=400, minimum_holdout=100):
    seen = set()
    clean = []
    for row in rows:
        if any(k not in row or row[k] in ("", None) for k in REQUIRED):
            raise ValueError("Missing historical goalie ID, outcome, or pregame feature")
        gid = str(row["game_id"])
        if gid in seen:
            raise ValueError("Duplicate training fixture")
        seen.add(gid)
        game_date = date.fromisoformat(row["date"])
        feature_date = date.fromisoformat(row["feature_as_of_date"])
        if feature_date >= game_date:
            raise ValueError("Pregame features must predate fixture date")
        if row["ml_winner"] not in ("home", "away"):
            raise ValueError("Invalid outcome")
        for name in ("home_goalie_id", "away_goalie_id"):
            if not str(row[name]).isdigit() or int(row[name]) <= 0:
                raise ValueError("Unknown goalie identity")
        for name in FEATURES:
            value = float(row[name])
            if not (float("-inf") < value < float("inf")):
                raise ValueError("Nonfinite sporting feature")
            if name.endswith("_sv") and not 0 <= value <= 1:
                raise ValueError("Invalid prior save percentage")
        clean.append(row)
    clean.sort(key=lambda x: (x["date"],str(x["game_id"])))
    # Calendar cutoffs must never share the same playing date between partitions.
    dates = sorted(set(x["date"] for x in clean))
    if len(dates) < 6:
        return {"status": "blocked_insufficient_historical_dates",
                "training_rows": len(clean), "fit_rows": 0,
                "validation_rows": 0, "holdout_rows": 0}
    train_end = dates[max(0, int(len(dates)*0.6)-1)]
    validation_end = dates[max(0, int(len(dates)*0.8)-1)]
    partitions = Counter("fit" if r["date"] <= train_end
                         else "validation" if r["date"] <= validation_end
                         else "holdout" for r in clean)
    ok = partitions["fit"] >= minimum_train and partitions["holdout"] >= minimum_holdout and partitions["validation"] >= 50
    return {"status": "eligible_for_fitting" if ok else "blocked_insufficient_historical_examples",
            "training_rows": len(clean), "fit_rows": partitions["fit"],
            "validation_rows": partitions["validation"], "holdout_rows": partitions["holdout"],
            "fit_through": train_end, "validation_through": validation_end,
            "required_features": list(FEATURES), "odds_used": False,
            "validated_model": False, "official_predictions": 0,
            "note": "Schema and chronological eligibility only. Independent calibration and predictive validation remain required."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with Path(args.labels).open(newline="") as f:
        rows = list(csv.DictReader(f))
    result = audit(rows)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))

if __name__ == "__main__":
    main()
