"""Diagnose the actual NBA pregame injury and starting-five data gap.

This module audits retrieval provenance. An available ESPN observation is never
upgraded to NBA official player status, nor to confirmed starters.
"""
import argparse,json
from pathlib import Path

def diagnose(snapshot,official,preview,sporting,joint,coverage):
    games=snapshot.get("predictions",[])
    if not isinstance(games,list) or not games:raise ValueError("Nonempty slate required")
    n=len(games)
    previews=preview.get("games",{})
    supplemental=sporting.get("games",{})
    merged=joint.get("games",{})
    per_game=[]
    reasons={}
    for row in games:
        gid=str(row["game_id"])
        view=previews.get(gid,{})
        injuries=supplemental.get(gid,{}).get("supplementary_injury_observations",{})
        settled=merged.get(gid,{})
        espn_preview_ok=view.get("is_pregame_evidence") is True
        espn_obs=len(view.get("injury_observations",[])) if espn_preview_ok else 0
        feed_obs=len(injuries.get("items",[])) if isinstance(injuries,dict) else 0
        detail={
            "game_id":gid,"home_team":row["home_team"],"away_team":row["away_team"],
            "espn_game_preview_available":espn_preview_ok,
            "espn_preview_injury_observations":espn_obs,
            "espn_supplementary_injury_observations":feed_obs,
            "nba_official_pdf_retrieved":official.get("official_document_retrieved") is True,
            "nba_official_player_team_status_verified":
                settled.get("official_player_team_status_confirmed") is True,
            "both_starting_fives_verified":settled.get("lineups_confirmed") is True,
            "ready_for_availability_calibration":False}
        missing=[]
        if not detail["nba_official_pdf_retrieved"]:missing.append("nba_pdf_unavailable")
        if not detail["nba_official_player_team_status_verified"]:missing.append("official_player_team_status_unresolved")
        if not detail["both_starting_fives_verified"]:missing.append("starting_fives_unverified")
        if not espn_preview_ok:missing.append("espn_preview_unavailable")
        for reason in missing:reasons[reason]=reasons.get(reason,0)+1
        detail["missing_evidence"]=missing
        per_game.append(detail)
    audit_total=coverage.get("games")
    if audit_total!=n:raise ValueError("Coverage file and slate differ")
    return {"schema_version":1,"sport":"nba","games":n,
        "complete_pregame_features":coverage.get("complete_pregame_features"),
        "official_source_retrieved":official.get("official_document_retrieved") is True,
        "official_pdf_retrieval_error":official.get("retrieval_error_type"),
        "raw_official_status_lines":sum(len(p.get("official_raw_status_lines",[])) for p in list(merged.values())[:1]),
        "missing_evidence_reasons":reasons,"per_game":per_game,
        "calibrated_availability_impact":False,
        "note":"ESPN injuries are supplementary observations, not verified official statuses. PDF availability alone does not certify player rows."}

def main():
    ap=argparse.ArgumentParser()
    for name in ("snapshot","official","preview","sporting","joint","coverage","output"):
        ap.add_argument("--"+name,required=True)
    a=ap.parse_args()
    load=lambda s:json.loads(Path(s).read_text()) if Path(s).is_file() else {}
    result=diagnose(*(load(getattr(a,name)) for name in ("snapshot","official","preview","sporting","joint","coverage")))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"games":result["games"],"coverage":result["complete_pregame_features"],
      "nba_official_pdf":result["official_source_retrieved"],"reasons":result["missing_evidence_reasons"]}))
if __name__=="__main__":main()
