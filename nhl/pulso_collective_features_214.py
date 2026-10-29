"""PULSO NHL #214 collective evidence vector — no unsourced rates or picks."""
import argparse,json,math
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def build(fixture,crs,goalie,context,as_of):
 cutoff=parse_utc(fixture["start_utc"]);issued=parse_utc(as_of)
 if issued>=cutoff:raise ValueError("Prediction time must predate puck drop")
 if str(crs.get("game_id"))!=str(fixture.get("game_id")):raise ValueError("CRS fixture mismatch")
 h,a=fixture["home"],fixture["away"]
 if context.get("home")!=h or context.get("away")!=a:raise ValueError("Context fixture mismatch")
 issues=list(crs.get("issues",[]));teams={}
 for team in (h,a):
  proxy=crs.get("skater_crs_proxies",{}).get(team,{})
  offense=proxy.get("crs_skater_offense_proxy")
  delta=proxy.get("availability_delta_skater_offense_proxy")
  if offense is None or delta is None:issues.append("missing_crs_"+team)
  g=[x for x in goalie.get("goalies",[]) if x.get("team")==team and str(x.get("game_id"))==str(fixture["game_id"])]
  if len(g)!=1:issues.append("missing_unique_goalie_"+team);ginfo=None
  else:
   ginfo=g[0]
   if ginfo.get("capture_as_of") is None or parse_utc(ginfo["capture_as_of"])>issued:
    issues.append("late_goalie_evidence_"+team)
   if not ginfo.get("sample_adequate"):issues.append("insufficient_goalie_history_"+team)
  st=context.get("special_teams",{}).get(team,{})
  pp=st.get("pp");pk=st.get("pk_opponent_conversions_allowed")
  if not pp or not pk:issues.append("missing_pp_pk_"+team)
  for part in (pp,pk):
   if part and (not part.get("as_of") or parse_utc(part["as_of"])>issued):issues.append("late_st_"+team)
  if team not in context.get("rest_days",{}) or context["rest_days"][team] is None:issues.append("unknown_rest_"+team)
  teams[team]={"offense_skater_proxy":offense,"availability_delta_proxy":delta,
    "goalie_historical_rating":ginfo.get("historical_goalie_rating") if ginfo else None,
    "goalie_id":ginfo.get("goalie_player_id") if ginfo else None,
    "pp_bayes":pp.get("beta_shrunk") if pp else None,"pk_opponent_allowed_bayes":pk.get("beta_shrunk") if pk else None,
    "rest_days":context.get("rest_days",{}).get(team)}
 return {"game_id":fixture["game_id"],"as_of":as_of,"status":"feature_vector_partial" if issues else "research_vector_complete",
  "teams":teams,"home_ice":context.get("home_ice"),"division":context.get("division"),
  "rivalry":context.get("rivalry"),"rivalry_tier":context.get("rivalry_tier"),
  "issues":sorted(set(issues)),"defensive_unit_rating":None,
  "goal_rates":None,"ml_probabilities":None,"rt_probabilities":None,"plus3_probabilities":None,
  "official":False,"model_trained_on_historical_asof":False,"odds_used":False}
def main():
 p=argparse.ArgumentParser()
 for name in ("fixture","crs","goalie","context","as-of","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 load=lambda x:json.loads(Path(getattr(a,x)).read_text())
 result=build(load("fixture"),load("crs"),load("goalie"),load("context"),a.as_of)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"status":result["status"],"issues":result["issues"]}))
if __name__=="__main__":main()
