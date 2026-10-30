"""#246 NHL official prior-date team sporting observations (not roster CRS).

Official standings furnish actual scoring form and observed PP/PK, not invented
starting goalies, injuries, lineup shares, per-player ability or calibrated ML.
The fetch timestamp and effective source date are retained for every fixture.
"""
import argparse,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from nhl.official_team_stats import collect
from nhl.pulso_pregame_v7 import parse_utc
HOST="https://api-web.nhle.com/v1/standings/"
def parse_date(d):
 return datetime.strptime(d,"%Y-%m-%d").date()
def last_completed_day(report):
 at=parse_utc(report["generated_at_utc"])
 # Even if games on the capture day are complete, use previous full UTC day.
 return (at.date()-timedelta(days=1)).isoformat()
def build(report,standings,source_url):
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Expected unpromoted capture report")
 at=parse_utc(report["generated_at_utc"])
 d=last_completed_day(report)
 if source_url!=HOST+d:raise ValueError("Dated source must match strictly prior day")
 allteams=collect(standings,source_url,at.isoformat())
 games=[]
 for f in report["games"]:
  if parse_utc(f["start_utc"])<=at:raise ValueError("Game is not future")
  sides={}
  for team in (f["home"],f["away"]):
   row=allteams.get(team)
   if row is None:
    sides[team]={"status":"missing","source_url":source_url,"features":None,"blocked":["standings_unavailable"]}
    continue
   n=row["gamesPlayed"]
   valid=n>=5 and all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in
     ("goals_for_per_game","goals_against_per_game","goal_diff_per_game_shrunk"))
   feats={"games_played":n,"goals_for_per_game":row["goals_for_per_game"],
    "goals_against_per_game":row["goals_against_per_game"],
    "goal_diff_per_game_shrunk":row["goal_diff_per_game_shrunk"],
    "pp_pct_observed":row["power_play_pct_observed"],
    "pk_pct_observed":row["penalty_kill_pct_observed"],
    "source_effective_day":d,"source_as_of_utc":at.isoformat(),
    "source_url":source_url}
   sides[team]={"status":"observed_not_calibrated" if valid else "insufficient_team_history",
    "features":feats,"blocked":[] if valid else ["team_history_under_five_games_or_invalid"]}
  games.append({"game_id":str(f["game_id"]),"home":f["home"],"away":f["away"],
    "start_utc":f["start_utc"],"sides":sides,"starter_confirmed":False,
    "lineups_confirmed":False,"pp_pk_sustainable_fitted":False,
    "applied_to_ml":False})
 return {"kind":"nhl_live_sporting_observations_246","observed_at_utc":at.isoformat(),
  "prior_completed_day":d,"source_url":source_url,"games":games,
  "calibrated":False,"official":False,"official_predictions":0,"odds_used":False,
  "limitations":["Season team-level standings are not current CRS or player availability.",
   "Observed PP/PK percentages are not bayesian count estimates or fitted effects.",
   "Starting goalie identity, GSAx, fatigue and travel remain unverified."]}
def main():
 p=argparse.ArgumentParser()
 for x in ("report","out"):p.add_argument("--"+x,required=True)
 p.add_argument("--standings",help="Optional local immutable prior-date NHL standings JSON")
 a=p.parse_args();report=json.loads(Path(a.report).read_text())
 d=last_completed_day(report);url=HOST+d
 if a.standings:standings=json.loads(Path(a.standings).read_text())
 else:
  with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"BeatBetano-research/1.0"}),timeout=30) as response:
   raw=response.read(2500000)
   if response.read(1):raise ValueError("Standings payload too large")
  standings=json.loads(raw)
 result=build(report,standings,url)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"games":len(result["games"]),"teams_with_evidence":sum(side["status"]=="observed_not_calibrated" for g in result["games"] for side in g["sides"].values()),"official_predictions":0}))
if __name__=="__main__":main()
