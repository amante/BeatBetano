"""Retrospective, leakage-safe NHL goalie daily evidence, NOT official Goalie Rating.

Only observations from game dates strictly before source capture day are allowed.
This uses historical saved shots / shots faced, not GSAx or causal goalie impact.
"""
import argparse,json,math
from pathlib import Path
from datetime import timezone
try:
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from roster_aware_units import timepoint

def assess(crosswalk,history_rows,rosters,min_games=3,prior_saves=90.5,prior_shots=100):
 if prior_shots<=0 or not 0<=prior_saves<=prior_shots or min_games<1:raise ValueError("Bad prior")
 rosters_by_team={r["team"]:r for r in rosters}
 # Previous-date history is frozen by date; do not read the same date as a forecast.
 indexed={(r["game_id"],side):r[side] for r in history_rows for side in ("home","away")}
 # For a forecast timestamp, choose latest historical snapshot with date earlier
 # than observed pregame date, including snapshots from unrelated games.
 teams={}
 for r in history_rows:
  for side in ("home","away"):
   team=r[side]["team"]
   teams.setdefault(team,[]).append((r["date"],r["game_id"],r[side]["players"]))
 for team in teams:teams[team].sort(key=lambda x:(x[0],x[1]))
 reports=[]
 for ob in crosswalk["observations"]:
  team=ob["team"];captured=timepoint(ob["source_captured_at"]).astimezone(timezone.utc).date().isoformat()
  past=[x for x in teams.get(team,[]) if x[0]<captured]
  h=past[-1][2] if past else {}
  roster=rosters_by_team.get(team,{"players":[]})
  def score(pid):
   rec=h.get(str(pid),{})
   n=rec.get("goalie_games",0);shots=rec.get("goalie_shots",0);saves=rec.get("goalie_saves",0)
   if n<min_games or shots<1 or saves<0 or saves>shots:return None
   return {"observed_games":n,"shots":shots,"saves":saves,"historical_sv_pct":round(saves/shots,6),
    "shrunk_sv_pct":round((saves+prior_saves)/(shots+prior_shots),6)}
  validated=ob.get("usable_pregame_identity") is True and ob.get("validation_errors")==[]
  goalie_id=ob.get("nhl_player_id") if validated else None
  primary=score(goalie_id) if goalie_id else None
  alternatives=[]
  for candidate in roster.get("players",[]):
   if candidate.get("position_group")!="goalie" or candidate["player_id"]==goalie_id:continue
   alternatives.append({"player_id":candidate["player_id"],"rating":score(candidate["player_id"])})
  # Only relative save percentage evidence, not wins/expected goals.
  comparison=[{"other_goalie_id":x["player_id"],
     "delta_shrunk_save_pct":round(primary["shrunk_sv_pct"]-x["rating"]["shrunk_sv_pct"],6)
       if primary and x["rating"] else None} for x in alternatives]
  reports.append({"team":team,"game_id":ob.get("nhl_game_id"),"source_goalie_status":ob.get("goalie_status"),
   "goalie_player_id":goalie_id,"capture_as_of":ob.get("source_captured_at"),
   "prior_history_date":past[-1][0] if past else None,
   "historical_goalie_rating":primary,"alternative_goalies":alternatives,
   "comparison":comparison,"sample_adequate":primary is not None,
   "goalie_daily_rating_official":None,"injury_fatigue_quality_adjusted":False,
   "uncertainty":"Prior-shrunk save percentage; no opponent xG, rest, medical or on-ice defense adjustments.",
   "eligible_for_official_crs":False})
 return {"games":len(reports),"rated":sum(x["sample_adequate"] for x in reports),
   "goalies":reports,"odds_used":False,"model_promoted":False,
   "definition":"Descriptive, prior-date team-history goalie SV% evidence; not Goalie Daily Rating official."}

def main():
 p=argparse.ArgumentParser()
 for k in ("crosswalk","history","rosters","output"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 result=assess(json.loads(Path(a.crosswalk).read_text()),json.loads(Path(a.history).read_text()),
               json.loads(Path(a.rosters).read_text()))
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"observations":result["games"],"historically_rated":result["rated"],
  "official_rating_promoted":False},indent=2))
if __name__=="__main__":main()
