"""Mandatory NBA full-pregame review gate.

Sports-model probabilities are only baselines. Without independently verified
lineups, injuries, matchup and quantified availability adjustments, no final
prediction or betting eligibility is produced. Never infer these from Elo.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
REQUIRED=("starting_lineups","injury_report","rotation_minutes",
          "player_matchups","team_form","rest_travel","availability_impact")
def review(snapshot,evidence=None):
    evidence=evidence or {}
    games=evidence.get("games",{})
    output=[]
    for p in snapshot["predictions"]:
        row=games.get(str(p["game_id"]),{})
        checks={key:bool(isinstance(row.get(key),dict) and
              row[key].get("verified") is True and row[key].get("source") and
              row[key].get("observed_at_utc")) for key in REQUIRED}
        all_verified=all(checks.values())
        adjustment=row.get("availability_impact",{})
        numerical=bool(all_verified and isinstance(adjustment.get("home_win_probability_delta"),(int,float))
             and not isinstance(adjustment.get("home_win_probability_delta"),bool)
             and -1<=adjustment["home_win_probability_delta"]<=1)
        # Do not imply the availability impact is calibrated merely because
        # someone populated an input field. An audit is required separately.
        approved=False
        output.append({"game_id":p["game_id"],"home_team":p["home_team"],
            "away_team":p["away_team"],"baseline_elo_p_home":p["elo_p_home"],
            "baseline_challenger_p_home":p["challenger_p_home"],
            "baseline_hybrid_p_home":p["hybrid_p_home"],
            "evidence_checks":checks,"evidence_verified":all_verified,
            "availability_delta_provided":numerical,
            "final_p_home":None,"final_model_approved":approved,
            "eligible_for_bet":False,
            "status":"review_required" if not all_verified else "impact_calibration_required"})
    return {"schema_version":1,"snapshot_sha256":snapshot["content_sha256"],
        "stage":"NBA_FULL_PREGAME_GATE","games":output,
        "all_games_final_approved":False,
        "note":"Never treat statistical baselines as complete pregame or betting approval."}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    snap=json.loads(Path(args.snapshot).read_text())
    evid=json.loads(Path(args.evidence).read_text()) if args.evidence else {}
    result=review(snap,evid)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({"reviewed":len(result["games"]),"final_approved":0,
        "review_required":sum(not x["evidence_verified"] for x in result["games"])},indent=2))
