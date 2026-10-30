"""PULSO NHL 222-223: fixture-level evidence coverage, no implied athletic ratings.

Consumes official pregame source capture artifacts, not match outcomes/odds.
"""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

FIELDS=("schedule","roster_pool","lineup_18_confirmed","skater_crs","availability_verified",
        "goalie_confirmed","goalie_history","defense_unit","pp","pk","rest","rivalry")
def analyze(report,roster,goalies,editorial,crs=None,collective=None):
 if report.get("data_kind")!="source_readiness_only":raise ValueError("Source report required")
 issued=parse_utc(report["generated_at_utc"])
 roster_teams=roster.get("rosters",{})
 if isinstance(roster_teams,list):roster_teams={x.get("team"):x for x in roster_teams if isinstance(x,dict)}
 goalie_records=goalies.get("goalies",[])
 results=[]
 for g in report["games"]:
  gid=str(g["game_id"]);start=parse_utc(g["start_utc"])
  if issued>=start:raise ValueError("Captured after start: "+gid)
  by_team={}
  for team in (g["home"],g["away"]):
   candidate=roster_teams.get(team)
   relevant=[x for x in goalie_records if x.get("team")==team and str(x.get("game_id"))==gid]
   flags={k:False for k in FIELDS}
   flags["schedule"]=True
   flags["roster_pool"]=bool(candidate)
   # A roster candidate pool / ESPN goalie assertion cannot confirm starters.
   if len(relevant)==1:
    item=relevant[0]
    if item.get("capture_as_of") and parse_utc(item["capture_as_of"])<=issued:
     flags["goalie_history"]=bool(item.get("sample_adequate") and item.get("historical_goalie_rating"))
   # Only explicit fixture-linked, pregame independently verified inputs qualify.
   c=(crs or {}).get(gid,{})
   if c.get("as_of") and parse_utc(c["as_of"])<=issued and c.get("availability_independently_verified") is True:
    flags["availability_verified"]=True
    flags["skater_crs"]=bool(c.get("skater_crs_proxies",{}).get(team))
   v=(collective or {}).get(gid,{})
   if v.get("as_of") and parse_utc(v["as_of"])<=issued and v.get("source_attestation_verified") is True:
    tv=v.get("teams",{}).get(team,{})
    flags["defense_unit"]=tv.get("defense_rating") is not None
    for field in ("pp","pk","rest"):
     flags[field]=tv.get(field) is not None
    flags["rivalry"]=v.get("rivalry") is not None
   # No canonical independently verified 18-skater/game-goalie signal in current sources.
   by_team[team]={"coverage":flags,"missing":[k for k,x in flags.items() if not x],
       "confirmed_starting_goalie_id":None,"confirmed_lineup":None}
  results.append({"game_id":gid,"home":g["home"],"away":g["away"],"as_of":report["generated_at_utc"],
    "teams":by_team,"sufficient_for_full_model":all(all(t["coverage"].values()) for t in by_team.values()),
    "official_probabilities":None})
 return {"kind":"collective_evidence_coverage","as_of":report["generated_at_utc"],
  "games":results,"full_model_ready":sum(x["sufficient_for_full_model"] for x in results),
  "total_games":len(results),"odds_used":False,"model_promoted":False,
  "note":"Editorial projections and roster pools do not independently verify starters."}
def main():
 p=argparse.ArgumentParser()
 for k in ("report","rosters","goalies","editorial","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args();read=lambda k:json.loads(Path(getattr(a,k)).read_text())
 result=analyze(read("report"),read("rosters"),read("goalies"),read("editorial"))
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2))
 print(json.dumps({"games":result["total_games"],"full_model_ready":result["full_model_ready"]}))
if __name__=="__main__":main()
