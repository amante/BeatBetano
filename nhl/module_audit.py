"""NHL module coverage audit. Never promote uncalibrated exploratory probabilities.

Runs after the slate/goalie collection. No prices or external odds are inputs.
Missing evidence stays missing; contextual flags never change probabilities.
"""
import argparse
import json
from pathlib import Path

# Real divisional membership for the 2026-27 NHL structure.
DIVISIONS = (
    {"BOS", "BUF", "DET", "FLA", "MTL", "OTT", "TBL", "TOR"},
    {"CAR", "CBJ", "NJD", "NYI", "NYR", "PHI", "PIT", "WSH"},
    {"CHI", "COL", "DAL", "MIN", "NSH", "STL", "UTA", "WPG"},
    {"ANA", "CGY", "EDM", "LAK", "SJS", "SEA", "VAN", "VGK"},
)
# Explicitly known high-intensity rivalries, not a claim of a complete registry.
TIER_A = (
    ("BOS", "MTL"), ("BOS", "TOR"), ("CGY", "EDM"),
    ("PHI", "PIT"), ("PIT", "WSH"), ("NYI", "NYR"),
    ("NJD", "NYR"), ("OTT", "TOR"), ("ANA", "LAK"),
    ("SJS", "VGK"), ("FLA", "TBL"),
)
RIVALRIES = {frozenset(pair): "A" for pair in TIER_A}
MODULES = (
    "crs", "unit_ratings", "goalie_daily", "sustainable_pp_pk",
    "division_rivalry", "official_ml", "challenger_ml",
    "regulation", "three_goal_lead", "dual_fuerte",
)

def context(home, away):
    divisional = any(home in group and away in group for group in DIVISIONS)
    tier = RIVALRIES.get(frozenset((home, away)))
    return {"divisional": divisional, "rivalry": tier is not None,
            "rivalry_tier": tier, "home_ice_team": home,
            "familiarity": "divisional_repetition" if divisional else "not_established",
            "probability_delta": None, "delta_calibrated": False}

def review(slate, goalies):
    if slate.get("sport") != "nhl" or goalies.get("sport") != "nhl":
        raise ValueError("NHL inputs required")
    if slate.get("as_of_utc") != goalies.get("as_of_utc"):
        raise ValueError("Point-in-time mismatch")
    records = []
    for game in slate.get("events", []):
        eid = str(game["event_id"])
        evidence = game.get("unit_strength_evidence") or {}
        goalie = game.get("goalie_daily_evidence") or {}
        observations = goalies.get("games", {}).get(eid, {})
        has_units = (isinstance(evidence, dict)
                     and all(isinstance(evidence.get(side), dict) and
                             evidence[side].get("full_evidence") is True
                             for side in ("home", "away")))
        goalie_measured = bool(observations) or any(
            isinstance(goalie.get(side), dict)
            and goalie[side].get("status") == "measured_unfitted"
            for side in ("home", "away"))
        goalie_confirmed = goalie.get("both_starters_confirmed") is True
        stats = game.get("official_team_stats") or {}
        pp_observed = all(isinstance(stats.get(side), dict)
                          and stats[side].get("power_play_pct_observed") is not None
                          and stats[side].get("penalty_kill_pct_observed") is not None
                          for side in ("home", "away"))
        ctx = context(game["home_team"], game["away_team"])
        details = {
            "crs": {"state": "unavailable", "reason": "no_validated_roster_weighting"},
            "unit_ratings": {"state": "evidence_only" if has_units else "missing",
                             "reason": "verified_inputs_not_probabilistic_weights" if has_units else "no_verified_unit_snapshots"},
            "goalie_daily": {"state": "evidence_only" if goalie_measured else "missing",
                             "confirmed_starters": goalie_confirmed,
                             "reason": "rating_and_impact_not_fitted" if goalie_measured else "goalie_evidence_missing"},
            "sustainable_pp_pk": {"state": "observed_only" if pp_observed else "missing",
                                   "reason": "observed_percentages_not_bayesian_strength"},
            "division_rivalry": {"state": "context_available", "context": ctx,
                                  "reason": "context_only_no_calibrated_probability_delta"},
            "official_ml": {"state": "unavailable", "reason": "official_baseline_not_fitted"},
            "challenger_ml": {"state": "unavailable", "reason": "independent_holdout_not_passed"},
            "regulation": {"state": "unavailable", "reason": "60_minute_distribution_not_fitted"},
            "three_goal_lead": {"state": "unavailable", "reason": "path_dependent_goal_lead_model_not_fitted"},
            "dual_fuerte": {"state": "blocked", "reason": "needs_validated_ml_rt_and_3glp"},
        }
        # Defensive guard: this audit must not transform exploratory probabilities into a pick.
        records.append({"event_id": eid, "home_team": game["home_team"],
                        "away_team": game["away_team"], "modules": details,
                        "exploratory_home_probability": game.get("statistical_p_home"),
                        "official_win_probability": None, "eligible_for_bet": False})
    return {"schema_version": 1, "sport": "nhl", "as_of_utc": slate["as_of_utc"],
            "module_names": list(MODULES), "audited_games": len(records),
            "games": records, "validated_probabilities": False,
            "note": "Diagnostics only. Do not interpret context flags as model adjustments."}

def markdown(report):
    rows = ["## NHL module coverage (not betting recommendations)",
            "All ten modules are displayed. Missing calibration is deliberately not replaced with guesses.",
            "", "| Matchup | CRS | Units | Goalie | PP/PK | Division/Rivalry | ML | Challenger | RT | +3 | DUAL/FUERTE |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for game in report["games"]:
        m = game["modules"]
        flags = m["division_rivalry"]["context"]
        label = ("Division" if flags["divisional"] else "Non-div.") + (
            "/Rivalry " + flags["rivalry_tier"] if flags["rivalry"] else "")
        cells = [game["away_team"] + " @ " + game["home_team"],
                 m["crs"]["state"], m["unit_ratings"]["state"],
                 m["goalie_daily"]["state"], m["sustainable_pp_pk"]["state"],
                 label, m["official_ml"]["state"], m["challenger_ml"]["state"],
                 m["regulation"]["state"], m["three_goal_lead"]["state"],
                 m["dual_fuerte"]["state"]]
        rows.append("| " + " | ".join(cells) + " |")
    rows.extend(["", "### Gate", "No final ML, regulation, +3 or DUAL/FUERTE recommendations are authorized by this report."])
    return "\n".join(rows) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--goalies", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()
    result = review(json.loads(Path(args.slate).read_text()),
                    json.loads(Path(args.goalies).read_text()))
    for path, value in ((args.output, json.dumps(result, indent=2)),
                        (args.summary, markdown(result))):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value)
    print(json.dumps({"audited_games": result["audited_games"], "module_count": len(MODULES),
                      "validated_probabilities": False}))

if __name__ == "__main__":
    main()
