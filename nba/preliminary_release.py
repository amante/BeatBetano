"""NBA decision-grade display: preserve baseline estimates without inventing validated finals."""
import argparse,json,math
from pathlib import Path

def publish(report):
    if report.get("command")!="NBA hoy" or report.get("complete_slate") is not True:
        raise ValueError("Complete NBA hoy report required")
    out=[]
    for row in report.get("games",[]):
        vals=[row.get(x) for x in ("official_baseline_p_home","challenger_baseline_p_home","hybrid_baseline_p_home")]
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1 for v in vals):
            raise ValueError("Invalid statistical probability")
        final=row.get("final_p_home")
        if final is not None and (row.get("final_status")!="validated_integrated_candidate" or
           type(final) not in (int,float) or not math.isfinite(final) or not 0<final<1):
            raise ValueError("Unapproved final")
        base=vals[2]
        out.append({"game_id":row["game_id"],"home_team":row["home_team"],
            "away_team":row["away_team"],"tipoff_utc":row["tipoff_utc"],
            "statistical_baseline_home":base,"statistical_baseline_away":round(1-base,6),
            "official_elo_home":vals[0],"challenger_home":vals[1],
            "preliminary_dual_screen":abs(2*base-1)<=.06+1e-12,
            "preliminary_not_validated":True,
            "integrated_home":final,"integrated_away":row.get("final_p_away"),
            "lineups_verified":row.get("starting_fives_confirmed") is True,
            "injuries_verified":row.get("official_injuries_resolved") is True,
            "missing_evidence":row.get("missing_evidence",[]),
            "bet_authorized":False})
    return {"schema_version":1,"sport":"nba","command":"NBA hoy",
        "games":out,"games_expected":report["games_expected"],
        "games_returned":len(out),"no_odds_input":True,
        "status":"preliminary_stats_with_integrated_when_independently_validated",
        "note":"Baseline probabilities are exploratory estimates; DUAL is screening only, not two recommended bets. No bets authorized."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    x=p.parse_args()
    result=publish(json.loads(Path(x.input).read_text()))
    target=Path(x.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2))
    print(json.dumps({"games":len(result["games"]),"preliminary":len(result["games"]),"bet_authorized":0}))
if __name__=="__main__":main()
