"""PULSO #249 — source-coverage audit, distinguishing roster IDs from actual lineups.

Joins original fixture-level identity (#248), player/goalie history gate (#247),
official previous-day team form (#246), and source capture. NEVER constructs
expected lineups from mere NHL roster membership. Its job is to expose the
remaining measurable coverage gap rather than fabricate official predictions.
"""
import argparse,json
from collections import Counter
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

BLOCKS=("roster_candidates","goalie_identity","goalie_confirmed","lineup",
        "individual_history","individual_metrics","team_form","sporting_probability")

def audit(report,identity,individual,team_form):
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Only sourced unpromoted pregame capture")
 at=parse_utc(report["generated_at_utc"])
 for doc,kind,key in ((identity,"nhl_fixture_identity_gate_248","as_of_utc"),
                      (individual,"nhl_individual_player_goalie_evidence_247","as_of_utc"),
                      (team_form,"nhl_live_sporting_observations_246","observed_at_utc")):
  if doc.get("kind")!=kind or parse_utc(doc[key])!=at:
   raise ValueError("Source kind or capture timestamp mismatch: "+kind)
 by_id=[]
 for doc in (identity,individual,team_form):
  current={}
  for row in doc["games"]:
   gid=str(row["game_id"])
   if gid in current:raise ValueError("Repeated fixture in evidence")
   current[gid]=row
  by_id.append(current)
 games=[];totals=Counter();blockers=Counter()
 for f in report["games"]:
  gid=str(f["game_id"])
  if parse_utc(f["start_utc"])<=at:raise ValueError("Non-pregame fixture")
  source_rows=[z.get(gid) for z in by_id]
  if any(x is None for x in source_rows):raise ValueError("Fixture missing source")
  for x in source_rows:
   if (x["home"],x["away"])!=(f["home"],f["away"]):raise ValueError("Wrong fixture-team mapping")
  ident,ind,form=source_rows
  records={}
  for team in (f["home"],f["away"]):
   idt=ident["teams"].get(team)
   ip=ind["teams"].get(team)
   ft=form["sides"].get(team)
   if any(x is None for x in (idt,ip,ft)):raise ValueError("Incomplete fixture-side mapping")
   has_roster=idt["roster_candidate_count"]>0
   has_goalie=type(idt["source_goalie_player_id"]) is int
   confirmed=idt["independent_goalie_confirmation"] is True
   has_lineup=idt["editorial_lineup_identity_verified"] is True and idt.get("expected_lineup") is not None
   has_individual=ip["status"]=="individual_evidence_observed_not_calibrated"
   has_delta=has_individual and isinstance(ip.get("availability_delta"),dict) and all(
    v is not None for v in ip["availability_delta"].values())
   has_team=ft["status"]=="observed_not_calibrated"
   status={"roster_candidates":has_roster,"goalie_identity":has_goalie,
    "goalie_confirmed":confirmed,"lineup":has_lineup,
    "individual_history":has_individual,"individual_metrics":has_delta,
    "team_form":has_team,"sporting_probability":False}
   failures=set(idt["blockers"]+ip["blockers"]+ft["blocked"])
   for key,value in status.items():
    if value:totals[key]+=1
    else:failures.add("missing_"+key)
   for issue in failures:blockers[issue]+=1
   records[team]={"evidence":status,"blockers":sorted(failures),
    "goalie_nhl_player_id":idt["source_goalie_player_id"],
    "goalie_source_status":idt["source_goalie_status"],
    "source_team_form":ft.get("features",{}).get("source_url") if has_team else None,
    "source_attestation":"roster_identity_not_lineup_confirmation"}
  games.append({"game_id":gid,"home":f["home"],"away":f["away"],
   "start_utc":f["start_utc"],"teams":records,"sporting_prediction_eligible":False})
 n=len(games)*2
 return {"kind":"nhl_pregame_source_coverage_249","as_of_utc":report["generated_at_utc"],
  "fixtures":len(games),"team_sides":n,"coverage":{k:{"observed":totals[k],"total":n,
   "percentage":round(100*totals[k]/n,2) if n else None} for k in BLOCKS},
  "blocker_frequency":dict(sorted(blockers.items())),"games":games,
  "official_predictions":0,"calibrated":False,"odds_used":False,
  "note":"Audit only. Does not invent availability, goalie confirmations, or forecast contributions."}

def main():
 p=argparse.ArgumentParser()
 for name in ("report","identity","individual","team-form","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 load=lambda name:json.loads(Path(getattr(a,name.replace("-","_"))).read_text())
 result=audit(load("report"),load("identity"),load("individual"),load("team-form"))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"fixtures":result["fixtures"],"coverage":result["coverage"],"official_predictions":0}))
if __name__=="__main__":main()
