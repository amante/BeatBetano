"""#228: join historical pre-date TEAM statistics to frozen NHL fixture evidence.

Historical team goalie save percentages DO NOT describe the projected starter.
They stay separate from #227 player-goalie numerical signal.
"""
import argparse,json,math
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def join(report,archive):
 if report.get("kind")!="sporting_source_bridge":raise ValueError("Expected sporting source bridge")
 by_team={}
 for entry in archive:
  if entry.get("source_class")!="earlier_dates_postgame_boxscores_only":raise ValueError("Unverified historical source")
  d=entry["date"]
  for side in ("home","away"):
   rec=entry.get(side,{})
   team=rec.get("team")
   if team:
    key=(d,team)
    if key in by_team:raise ValueError("Duplicate historical team/date")
    by_team[key]=rec
 result={}
 for gid,g in report["games"].items():
  start=parse_utc(g["start_utc"]);issued=parse_utc(g["as_of"])
  if issued>=start:raise ValueError("Capture not pregame")
  day=start.date().isoformat()
  teams={}
  for team in (g["home"],g["away"]):
   rec=by_team.get((day,team))
   if rec is None:
    teams[team]={"status":"no_matching_prior_date_team_snapshot","features":None}
    continue
   goalie=rec.get("prior_goalie_save_pct");scoring=rec.get("prior_skater_goals_per_observed_game")
   count=rec.get("past_goalie_observation_games",0)
   if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (count,)) or count<0:raise ValueError("Invalid sample")
   if goalie is not None and (not isinstance(goalie,(int,float)) or not 0<=goalie<=1):raise ValueError("Invalid save percentage")
   if scoring is not None and (not isinstance(scoring,(int,float)) or scoring<0):raise ValueError("Invalid goals rate")
   teams[team]={"status":"historical_team_context_only",
    "features":{"team_prior_goalie_save_pct":goalie,"team_prior_skater_goals_per_game":scoring,
     "goalie_observation_games":count},
    "confirmed_starting_goalie":False,"current_lineup_verified":False,
    "source_class":"earlier_dates_postgame_boxscores_only"}
  result[gid]={"game_id":gid,"teams":teams,"start_utc":g["start_utc"],"as_of":g["as_of"]}
 return {"kind":"historical_team_context_research","games":result,
  "official":False,"odds_used":False,"full_model_ready":False,
  "note":"Aggregates include prior team goalies, not the actual starting goalie."}
def main():
 p=argparse.ArgumentParser()
 for k in ("bridge","history","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 data=join(json.loads(Path(a.bridge).read_text()),json.loads(Path(a.history).read_text()))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,indent=2))
 print(json.dumps({"fixtures":len(data["games"]),"with_history":sum(1 for g in data["games"].values() for t in g["teams"].values() if t["features"] is not None)}))
if __name__=="__main__":main()
