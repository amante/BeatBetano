"""PULSO player-to-team pregame research bridge.

Strictly pregame, duplicate-safe and coverage-gated. Aggregated player estimates
are descriptive features, NOT trained team goals or validated ML/RT/+3.
"""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def aggregate(fixture,players,goalie_crosswalk,minimum=12):
 start=parse_utc(fixture["start_utc"])
 teams=(fixture["home"],fixture["away"])
 if teams[0]==teams[1] or not fixture.get("game_id"):raise ValueError("Invalid fixture")
 by=defaultdict(list);seen=set();errors=[]
 for row in players:
  team=row.get("team");pid=str(row.get("player_id",""))
  if team not in teams or not pid.isdigit():raise ValueError("Unexpected player")
  key=(team,pid)
  if key in seen:raise ValueError("Duplicate player")
  seen.add(key)
  if row.get("availability") not in ("confirmed","probable"):
   errors.append("uncertain_player_"+team);continue
  if not row.get("asof_utc") or parse_utc(row["asof_utc"])>=start:
   errors.append("late_player_source_"+team);continue
  forecast=row.get("forecast") or {}
  values=forecast.get("projection")
  if not isinstance(values,dict):errors.append("missing_player_projection_"+team);continue
  if not all(type(values.get(x)) in (int,float) and math.isfinite(values[x]) and values[x]>=0 for x in ("toi_minutes","shots_on_goal","goals")):
   errors.append("invalid_player_prediction_"+team);continue
  by[team].append(row)
 summary={}
 for team in teams:
  rows=by[team];t=sum(p["forecast"]["projection"]["toi_minutes"] for p in rows)
  summary[team]={"skaters_forecasted":len(rows),
   "projected_skater_toi_sum":round(t,3),
   "sog_volume_proxy":round(sum(p["forecast"]["projection"]["shots_on_goal"] for p in rows),3),
   "player_goal_proxy":round(sum(p["forecast"]["projection"]["goals"] for p in rows),3),
   "coverage_ready":len(rows)>=minimum}
  if len(rows)<minimum:errors.append("insufficient_player_coverage_"+team)
 # Goalie crosswalk is source asserted, not official line starter evidence.
 goalie_rows=goalie_crosswalk.get("observations",[])
 goalie_status={}
 for team in teams:
  linked=[g for g in goalie_rows if g.get("team")==team and str(g.get("nhl_game_id"))==str(fixture["game_id"])
    and g.get("usable_pregame_identity") and g.get("nhl_player_id") is not None
    and g.get("source_captured_at") and parse_utc(g["source_captured_at"])<start]
  goalie_status[team]={"identities_linked":len(linked),"starter_independently_confirmed":False}
  if len(linked)!=1:errors.append("goalie_identity_unresolved_"+team)
 errors=sorted(set(errors))
 return {"game_id":str(fixture["game_id"]),"home":teams[0],"away":teams[1],
   "start_utc":fixture["start_utc"],"team_features":summary,"goalie_evidence":goalie_status,
   "status":"research_features_only" if not errors else "blocked_incomplete_evidence",
   "readiness_issues":errors,"collective_goal_rates":None,"probabilities":None,
   "official":False,"calibrated":False,"odds_used_in_model":False,
   "warning":"Skater sums are NOT team goal rates; team-level fitted coefficients and defensive/goalie corrections absent."}
def main():
 p=argparse.ArgumentParser()
 for k in ("fixture","players","goalies","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 def read(k):return json.loads(Path(getattr(a,k)).read_text())
 player_data=read("players")
 rows=player_data.get("player_predictions",[]) if isinstance(player_data,dict) else player_data
 result=aggregate(read("fixture"),rows,read("goalies"))
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2))
 print(json.dumps({"status":result["status"],"issues":result["readiness_issues"],"team_features":result["team_features"]},indent=2))
if __name__=="__main__":main()
