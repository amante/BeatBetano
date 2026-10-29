"""PULSO v8/v9: strictly gated NHL pregame research simulation and publication.

This adapter does NOT represent the calibrated official NHL model.
No complete source evidence => no probabilities. No market odds used.
"""
import argparse,json,math
from datetime import datetime,timezone
from pathlib import Path
from nhl.pulso_pregame_v7 import audit_snapshot,parse_utc
from nhl.goal_process import calculate

def finite_rate(value):
 if type(value) not in (float,int) or not math.isfinite(value) or not 0<value<10:
  raise ValueError("Invalid pregame rate")
 return float(value)

def verify_fixture(fixture,snapshot,goalies,evidence):
 start=fixture["start_utc"]
 cutoff=parse_utc(start)
 if cutoff<=datetime.now(timezone.utc) and not fixture.get("historical_audit_only"):
  return ["fixture_already_started"]
 issues=[]
 if fixture.get("game_id")!=snapshot.get("game_id") or fixture.get("home")!=snapshot.get("home_team") or fixture.get("away")!=snapshot.get("away_team"):
  issues.append("fixture_roster_mismatch")
 try:
  audit=audit_snapshot(snapshot,start)
  if not audit["eligible_for_full_team_prediction"]:issues.append("incomplete_or_ambiguous_skaters")
 except (ValueError,KeyError) as exc:
  issues.append("invalid_pregame_snapshot:"+str(exc))
 if not isinstance(goalies,list):goalies=[]
 for team in (fixture["home"],fixture["away"]):
  candidates=[g for g in goalies if g.get("team")==team and str(g.get("game_id"))==str(fixture["game_id"])]
  if len(candidates)!=1:issues.append("missing_goalie_"+team);continue
  g=candidates[0]
  if g.get("status")!="confirmed" or not g.get("confirmation_evidence_url") or not str(g.get("source_url","")).startswith("https://"):
   issues.append("unconfirmed_goalie_"+team)
  try:
   if parse_utc(g["asof_utc"])>=cutoff:issues.append("late_goalie_"+team)
  except (KeyError,ValueError):issues.append("missing_goalie_timestamp_"+team)
 if not isinstance(evidence,dict) or not evidence.get("source_url") or not str(evidence["source_url"]).startswith("https://"):
  issues.append("missing_scoring_source")
 else:
  try:
   if parse_utc(evidence["asof_utc"])>=cutoff:issues.append("late_scoring_source")
  except (KeyError,ValueError):issues.append("missing_scoring_timestamp")
 for module in ("crs","units","goalie","special_teams","context","rivalry"):
  if not isinstance(evidence,dict) or not isinstance(evidence.get(module),dict) or evidence[module].get("verified") is not True:
   issues.append("missing_verified_"+module)
 return issues

def publish(fixture,snapshot,goalies,evidence):
 """Return meaningful research diagnostics; never claim official probabilities."""
 issues=verify_fixture(fixture,snapshot,goalies,evidence)
 base={"sport":"nhl","game_id":str(fixture["game_id"]),"home":fixture["home"],"away":fixture["away"],
       "start_utc":fixture["start_utc"],"model_version":"pulso_v8_v9_research",
       "odds_used_in_model":False,"calibrated":False,"official":False,"bet_authorized":False,
       "point_in_time_sources_verified":not bool(issues),"readiness_issues":issues}
 if issues:return {**base,"status":"unavailable","probabilities":None}
 try:
  rates=evidence["rates"]
  lh=finite_rate(rates["home"]);la=finite_rate(rates["away"])
 except (TypeError,KeyError,ValueError):
  return {**base,"status":"unavailable","readiness_issues":["missing_valid_scoring_rates"],"point_in_time_sources_verified":False,"probabilities":None}
 metrics=calculate(lh,la)
 return {**base,"status":"research_only_not_calibrated",
  "probabilities":{"regulation":metrics["regulation"],"illustrative_ml":metrics["illustrative_ml"],
    "three_goal_lead":metrics["three_goal_lead"],"first_to_three_goal_lead":metrics["first_to_three_goal_lead"]},
  "source_urls":{"roster":snapshot["source_url"],"scoring":evidence["source_url"],
    "goalies":[g["source_url"] for g in goalies]},
  "warning":"Provisional Poisson goal-process model; module verification is not fitted causal influence. No betting recommendations."}

def main():
 p=argparse.ArgumentParser()
 for key in ("fixture","snapshot","goalies","evidence","out"):p.add_argument("--"+key,required=True)
 args=p.parse_args()
 def read(name):return json.loads(Path(getattr(args,name)).read_text())
 result=publish(read("fixture"),read("snapshot"),read("goalies"),read("evidence"))
 dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps({"generated_at_utc":datetime.now(timezone.utc).isoformat(),"games":[result]},indent=2))
 print(json.dumps({"status":result["status"],"issues":result["readiness_issues"]}))
if __name__=="__main__":main()
