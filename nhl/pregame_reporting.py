"""Render the actual cached current-season NHL evidence, not legacy empty feeds."""
import argparse,json
from pathlib import Path
def report(data):
    games=data.get("games",[])
    if not games:raise ValueError("No pregame evidence games")
    lines=["## NHL current-season evidence — actual cached 2026–27 source","",
      "This report supersedes legacy blank PP/PK and empty skater tables. Season statistics are descriptive; game rosters, goaltender starters and calibrated ratings remain unverified.","",
      f'**Games:** {len(games)} · **Snapshot age:** {data.get("snapshot_age_hours")} hours · **Historical queries:** 0',"",
      "| Matchup | F/D skaters (away/home) | Goalie candidates (away/home) | PP% (away/home) | PK% (away/home) | Verified ratings |",
      "|---|---|---|---|---|---|"]
    teams=set();skater_teams=0;pp_teams=0
    def val(x):
        return "—" if x is None else str(round(x,3)) if isinstance(x,(int,float)) else str(x)
    for g in games:
        h=g["home_evidence"];a=g["away_evidence"]
        for key,side in ((g["home_team"],h),(g["away_team"],a)):
            if key not in teams:
                teams.add(key)
                u=side["unit_evidence"];s=side["special_teams_evidence"]
                if u["forwards"]["players_with_stats"]+u["defense"]["players_with_stats"]>0:skater_teams+=1
                if s["power_play_pct_observed"] is not None and s["penalty_kill_pct_observed"] is not None:pp_teams+=1
        def sk(z):
            u=z["unit_evidence"]
            return f'{u["forwards"]["players_with_stats"]}/{u["defense"]["players_with_stats"]}'
        def goalies(z):return len(z["goalie_evidence"]["candidates"])
        def special(z,key):return val(z["special_teams_evidence"][key])
        lines.append(f'| {g["away_team"]} @ {g["home_team"]} | {sk(a)} / {sk(h)} | {goalies(a)} / {goalies(h)} | {special(a,"power_play_pct_observed")} / {special(h,"power_play_pct_observed")} | {special(a,"penalty_kill_pct_observed")} / {special(h,"penalty_kill_pct_observed")} | Not calibrated |')
    lines += ["",f"**Team coverage:** {len(teams)} teams; {skater_teams} with skater records; {pp_teams} with observed PP/PK.","",
      "**Outstanding inputs:** lineup verification, confirmed starting goalies, PP/PK opportunities, historical walk-forward fitting, ML/RT/3GLP and challenger calibration.",
      "**Odds used:** No."]
    return "\n".join(lines)+"\n",{"games":len(games),"teams":len(teams),"teams_with_skaters":skater_teams,"teams_with_pp_pk":pp_teams}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--summary",required=True)
    a=p.parse_args()
    md,metrics=report(json.loads(Path(a.input).read_text()))
    path=Path(a.summary);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(md)
    print(json.dumps(metrics))
    if metrics["teams_with_skaters"]<metrics["teams"] or metrics["teams_with_pp_pk"]<metrics["teams"]:
        raise SystemExit("Incomplete current-season skater or PP/PK evidence: report generated")
if __name__=="__main__":main()
