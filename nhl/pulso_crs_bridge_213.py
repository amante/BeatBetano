"""Fixture-specific, fail-closed CRS/availability *research* integration.

All historical and lineup sources must predate fixture start. Numerical skater
proxy is observational; no goalie, defense, team goal rates or official ML.
"""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc
from nhl.quantitative_roster_delta import compare

def integrate(fixture,coverage,inputs):
 start=parse_utc(fixture["start_utc"])
 if str(coverage.get("game_id"))!=str(fixture["game_id"]):raise ValueError("Fixture identity mismatch")
 if coverage.get("available_for_numeric_crs") is not False:raise ValueError("Unexpected CRS eligibility flag")
 if not coverage.get("projection_identity_coverage_complete"):return {"status":"blocked","issues":["incomplete_lineup_identity"],"probabilities":None}
 if parse_utc(coverage["captured_at"])>=start:raise ValueError("Post-start editorial source")
 result={};issues=[]
 teams={t["team"]:t for t in coverage["teams"]}
 for team in (fixture["home"],fixture["away"]):
  if team not in teams or team not in inputs:
   issues.append("missing_team_"+team);continue
  data=inputs[team];ids=set(teams[team]["projected_skater_ids"])
  expected=data["expected"];baseline=data["baseline"];history=data["history"]
  projected={str(p["player_id"]) for p in expected["players"] if p["status"]!="out" and p["unit"]!="goalie"}
  if projected!=ids:issues.append("lineup_mismatch_"+team);continue
  if parse_utc(expected["as_of"])>=start or parse_utc(baseline["as_of"])>=start or parse_utc(history["as_of"])>=start:
   issues.append("late_evidence_"+team);continue
  if not data.get("availability_independently_verified"):
   issues.append("unverified_availability_"+team);continue
  delta=compare(history,baseline,expected,fixture["start_utc"])
  result[team]=delta
  if delta["availability_delta_skater_offense_proxy"] is None:issues.append("incomplete_history_"+team)
 issues=sorted(set(issues))
 return {"game_id":fixture["game_id"],"status":"blocked" if issues else "research_skater_proxy_only",
  "issues":issues,"skater_crs_proxies":result,"goalie_rating":None,"defense_rating":None,
  "official_team_rates":None,"probabilities":None,"official":False,
  "note":"Availability verification must be independently provided. No full CRS or calibrated ML/RT/+3."}
def main():
 p=argparse.ArgumentParser()
 for name in ("fixture","coverage","inputs","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 f=lambda x:json.loads(Path(getattr(a,x)).read_text())
 result=integrate(f("fixture"),f("coverage"),f("inputs"))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"status":result["status"],"issues":result["issues"]}))
if __name__=="__main__":main()
