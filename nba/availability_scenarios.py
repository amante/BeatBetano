"""Scenario-bound NBA joint minutes: no unverified athlete silently deemed active.

Questionable players produce explicit in/out branches, never a default
betting probability. Unknown roster or status blocks allocation.
"""
import argparse,itertools,json
from pathlib import Path
from joint_minutes_report import build

def scenarios(snapshot,rotation,availability,max_questionable=3):
 if availability.get("snapshot_sha256")!=snapshot.get("content_sha256"):
  raise ValueError("Digest mismatch")
 outcome={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);original=availability.get("games",{}).get(gid,{}).get("teams",{})
  teams={}
  for team in (game["home_team"],game["away_team"]):
   info=original.get(team,{})
   players=info.get("players",[])
   if not info.get("roster_complete") or not isinstance(players,list) or not players:
    teams[team]={"status":"missing_complete_roster","branches":[]};continue
   if not info.get("observed_at_utc"):
    teams[team]={"status":"missing_source_time","branches":[]};continue
   unknown=[p["player_id"] for p in players if p.get("status")=="unknown"]
   uncertain=[p["player_id"] for p in players if p.get("status")=="questionable"]
   if unknown:
    teams[team]={"status":"unknown_availability_blocks","unknown_player_ids":unknown,"branches":[]};continue
   if len(uncertain)>max_questionable:
    teams[team]={"status":"too_many_unresolved_scenarios","questionable_count":len(uncertain),"branches":[]};continue
   branches=[]
   for choices in itertools.product(("available","out"),repeat=len(uncertain)):
    statuses=dict(zip(uncertain,choices))
    fork={"snapshot_sha256":snapshot["content_sha256"],"games":{gid:{"teams":{team:{
      **info,"availability_source_verified":True,
      "players":[{**p,"status":statuses.get(p["player_id"],p["status"])} for p in players]
    }}}}}
    # Re-use original joint budget and chronology constraints.
    try:
     one=build({"content_sha256":snapshot["content_sha256"],"predictions":[{
       **game,"home_team":team,"away_team":"__SCENARIO_PLACEHOLDER__"
     }]},rotation,fork)["games"][gid]["teams"][team]
    except (KeyError,ValueError) as exc:
     one={"status":"allocation_error","allocations":None,"detail":str(exc)}
    branches.append({"questionable_assumptions":statuses,"status":one["status"],
     "allocations":one.get("allocations"),"scenario_probability":None})
   teams[team]={"status":"scenarios_generated" if branches else "no_scenarios",
    "questionable_player_ids":uncertain,"branches":branches,
    "probability_weighted_minutes":None,
    "note":"Scenarios have no assigned weights; no certified active roster or lineup confirmation inferred."}
  outcome[gid]={"teams":teams}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":outcome,
  "no_odds_input":True,"production_probabilities_adjusted":False}
def main():
 a=argparse.ArgumentParser()
 for name in ("snapshot","rotation","availability","output"):a.add_argument("--"+name,required=True)
 q=a.parse_args()
 read=lambda x:json.loads(Path(x).read_text())
 out=scenarios(read(q.snapshot),read(q.rotation),read(q.availability))
 path=Path(q.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,indent=2))
 print(json.dumps({"games":len(out["games"]),"branches":sum(len(t["branches"]) for g in out["games"].values() for t in g["teams"].values())}))
if __name__=="__main__":main()
