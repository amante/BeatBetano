"""#259: fail-closed integration of goalie scenarios with fitted sporting forecasts.

The adapter NEVER infers probabilities from save percentages, roster membership,
outcome-only baselines or betting odds. Conditional probabilities require a
separately validated, point-in-time model output for the exact goalie pairing.
"""
import argparse
import json
import math
from pathlib import Path
from nhl.pulso_goalie_scenarios_258 import MARKETS
from nhl.pulso_pregame_v7 import parse_utc

GROUPS = (
    ("ml_home", "ml_away"),
    ("rt_home", "rt_draw", "rt_away"),
)
REQUIRED_MODEL = "nhl_fitted_goalie_conditional_259"

def _valid_probabilities(probs):
    if not isinstance(probs, dict) or set(probs) != set(MARKETS):
        return False
    if any(type(probs[key]) not in (int, float) or not math.isfinite(probs[key])
           or not 0 <= probs[key] <= 1 for key in MARKETS):
        return False
    if any(abs(sum(probs[k] for k in group) - 1) > 0.00001 for group in GROUPS):
        return False
    return True

def integrate(scenarios, model=None):
    if scenarios.get("kind") != "nhl_goalie_conditional_scenarios_258" or scenarios.get("odds_used") is not False:
        raise ValueError("Incorrect prospective scenario evidence")
    at = parse_utc(scenarios["as_of_utc"])
    records = {}
    if model is not None:
        if (model.get("kind") != REQUIRED_MODEL or model.get("odds_used") is not False
            or model.get("calibrated") is not True
            or model.get("walk_forward_validated") is not True
            or parse_utc(model["as_of_utc"]) < at):
            raise ValueError("Missing validated point-in-time conditional model")
        for record in model.get("predictions", []):
            key = (str(record["game_id"]), record["home_goalie_id"], record["away_goalie_id"])
            if key in records:
                raise ValueError("Duplicate scenario predictions")
            if any(type(k) is not int or k <= 0 for k in key[1:]):
                raise ValueError("Invalid goalie identity")
            records[key] = record
    output = []
    used = set()
    ready = 0
    for game in scenarios["games"]:
        gid = str(game["game_id"])
        result = {k: game[k] for k in ("game_id", "home", "away", "scenario_count")}
        pairs = []
        for pair in game["scenarios"]:
            h, a = pair["home_goalie"], pair["away_goalie"]
            key = gid, h["player_id"], a["player_id"]
            p = records.get(key)
            status = "awaiting_validated_conditional_forecast"
            probabilities = {k: None for k in MARKETS}
            if p is not None:
                if (p.get("home") != game["home"] or p.get("away") != game["away"]
                    or p.get("home_goalie_name") != h["name"]
                    or p.get("away_goalie_name") != a["name"]
                    or parse_utc(p["computed_at_utc"]) < at
                    or parse_utc(p["computed_at_utc"]) >= parse_utc(p["start_utc"])
                    or not _valid_probabilities(p.get("probabilities"))
                    or p.get("odds_used") is not False):
                    raise ValueError("Unverified or incoherent goalie forecast")
                used.add(key)
                probabilities = p["probabilities"]
                status = "experimental_conditional_validated"
                ready += 1
            pairs.append({"home_goalie": h, "away_goalie": a,
                          "probabilities": probabilities, "prediction_status": status,
                          "auto_pass": False, "official": False})
        result["scenarios"] = pairs
        output.append(result)
    if set(records) != used:
        raise ValueError("Predictions reference absent fixture/goalie combinations")
    return {"kind": "nhl_goalie_conditioned_forecast_259",
            "as_of_utc": scenarios["as_of_utc"], "games": output,
            "scenario_count": sum(g["scenario_count"] for g in output),
            "validated_experimental_scenarios": ready,
            "blocked_scenarios": sum(g["scenario_count"] for g in output) - ready,
            "official_predictions": 0, "odds_used": False,
            "note": "Only independent, validated conditional sporting forecasts may fill percentages; missing calibration stays null."}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", required=True)
    p.add_argument("--model", help="Verified fitted conditional model output (optional)")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    source = json.loads(Path(a.scenarios).read_text())
    model = json.loads(Path(a.model).read_text()) if a.model else None
    result = integrate(source, model)
    target = Path(a.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("scenario_count", "validated_experimental_scenarios", "blocked_scenarios", "official_predictions")}))
if __name__ == "__main__":
    main()
