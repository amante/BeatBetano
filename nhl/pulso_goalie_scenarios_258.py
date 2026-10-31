"""Pregame goalie-conditioned scenario matrix; no invented probabilities."""
import argparse,json,itertools
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

MARKETS=("ml_home","ml_away","rt_home","rt_draw","rt_away",
 "three_goal_lead_home","three_goal_lead_away","first_plus3_home",
 "first_plus3_away","rescue_home","rescue_away")
def build(report,identity,external,forecasts=None):
 at=parse_utc(report["generated_at_utc"])
 if identity.get("kind")!="nhl_fixture_identity_gate_248" or parse_utc(identity["as_of_utc"])!=at:raise ValueError("Bad identity evidence")
 if external.get("kind")!="nhl_external_goalie_observations_257" or parse_utc(external["as_of_utc"])!=at:raise ValueError("Bad provider evidence")
 ig={str(g["game_id"]):g for g in identity["games"]}
 eg={}
 for ob in external["observations"]:
  key=(str(ob["game_id"]),ob["team"])
  if key in eg:raise ValueError("Ambiguous external candidate")
  eg[key]=ob
 games=[]
 for f in report["games"]:
  gid=str(f["game_id"]);g=ig.get(gid)
  if g is None or (g["home"],g["away"])!=(f["home"],f["away"]):raise ValueError("Fixture mismatch")
  if at>=parse_utc(f["start_utc"]):raise ValueError("Fixture not pregame")
  candidates={}
  for team in (f["home"],f["away"]):
   r=g["teams"][team];items=[]
   pid=r.get("source_goalie_player_id")
   if type(pid) is int:items.append({"player_id":pid,"name":r.get("source_goalie_name") or "Nombre no disponible","source":"ESPN/NHL roster","status":"candidate"})
   e=eg.get((gid,team))
   if e:
    ep=e["player_id"]
    if type(ep) is not int:raise ValueError("Invalid external player ID")
    if not any(v["player_id"]==ep for v in items):
     items.append({"player_id":ep,"name":e["name"],"source":"Daily Faceoff/NHL roster","status":e["provider_status"]})
    else:
     next(v for v in items if v["player_id"]==ep)["status"]=e["provider_status"]
   candidates[team]=items
  scenarios=[]
  for h,a in itertools.product(candidates[f["home"]],candidates[f["away"]]):
   scenarios.append({"home_goalie":h,"away_goalie":a,
    "probabilities":{m:None for m in MARKETS},"prediction_status":"awaiting_fitted_sporting_model",
    "auto_pass":False})
  games.append({"game_id":gid,"home":f["home"],"away":f["away"],"goalie_candidates":candidates,
   "scenarios":scenarios,"scenario_count":len(scenarios)})
 return {"kind":"nhl_goalie_conditional_scenarios_258","as_of_utc":report["generated_at_utc"],
   "games":games,"official_predictions":0,"odds_used":False,
   "note":"Precomputes exact goalie pairings; percentages remain unavailable until validated calibrated sporting model."}
def main():
 p=argparse.ArgumentParser()
 for x in ("report","identity","external","out"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 x=build(*[json.loads(Path(getattr(a,k)).read_text()) for k in ("report","identity","external")])
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,indent=2))
 for g in x["games"]:
  print(f'{g["away"]}@{g["home"]}: {g["scenario_count"]} combinations')
  for sc in g["scenarios"]:
   print(f'  {sc["home_goalie"]["name"]} vs {sc["away_goalie"]["name"]}: ML pending calibration')
if __name__=="__main__":main()
