"""Build joint NBA regulation minutes from timestamped eligible roster and historical usage.

No roster or verified statuses => no allocation. Historical candidate lists alone
are NEVER treated as the current roster. Source must precede game tipoff.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from rotation_allocation_adapter import project_nba_minutes

def stamp(raw):
 try:
  t=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
  return t.astimezone(timezone.utc) if t.tzinfo else None
 except (ValueError,TypeError):return None

def build(snapshot,rotation,availability):
 if snapshot.get("content_sha256")!=rotation.get("snapshot_sha256"):
  raise ValueError("Historical rotation / snapshot mismatch")
 if availability.get("snapshot_sha256")!=snapshot.get("content_sha256"):
  raise ValueError("Availability / snapshot mismatch")
 out={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=stamp(game["tipoff_utc"])
  event=availability.get("games",{}).get(gid,{})
  archive=rotation.get("games",{}).get(gid,{})
  teams={}
  for team in (game["home_team"],game["away_team"]):
   evidence=event.get("teams",{}).get(team,{})
   roster=evidence.get("players",[])
   recorded=stamp(evidence.get("observed_at_utc"))
   if not recorded or not tip or recorded>=tip or not evidence.get("roster_complete") or not evidence.get("availability_source_verified"):
    teams[team]={"status":"current_roster_or_availability_unverified","allocations":None}
    continue
   historical={p["player_id"]:p for p in archive.get("teams",{}).get(team,{}).get("provisional_rotation",[])}
   players=[];reasons=[]
   for player in roster:
    pid=str(player.get("player_id") or "")
    if not pid or pid not in historical:
     reasons.append(pid or "missing_player_id")
     continue
    avg=historical[pid].get("minutes_projection")
    status=player.get("status","unknown")
    # Historical model remains descriptive; cap is a roster-evidence setting.
    players.append({"player_id":pid,"status":status,"expected_weight":avg if isinstance(avg,(int,float)) and avg>=0 else 0,
     "max_units":player.get("max_minutes",48)})
   if reasons:
    teams[team]={"status":"missing_historical_player_weights","player_ids":reasons,"allocations":None}
    continue
   result=project_nba_minutes({"roster_complete":True,"availability_source_verified":True,"players":players})
   if result.get("allocations") is not None and abs(sum(result["allocations"].values())-240)>0.001:
    raise ValueError("NBA minutes do not sum to 240")
   teams[team]={"status":result["status"],"allocations":result.get("allocations"),
    "eligible_players":sum(p["status"]=="available" for p in players),
    "historical_weight_method":"last_five_completed_appearances",
    "input_observed_at_utc":evidence["observed_at_utc"],
    "limitations":"Joint capped allocation, not yet position/lineup optimized nor absence-response fitted"}
  out[gid]={"teams":teams,"tipoff_utc":game["tipoff_utc"]}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":out,"sport":"nba",
  "probabilities_adjusted":False,"no_odds_input":True}

def markdown(report):
 rows=["## NBA — Constrained minutes allocation (pregame evidence gated)","",
 "| Game ID | Team | Status | Assigned minutes |",
 "|---|---|---|---:|"]
 for gid,g in report["games"].items():
  for team,r in g["teams"].items():
   mins=sum(r["allocations"].values()) if r.get("allocations") is not None else None
   rows.append(f'| {gid} | {team} | {r["status"]} | {round(mins,1) if mins is not None else "—"} |')
 rows.extend(["","Historical player minutes without current verified roster and statuses are deliberately not redistributed. No change to frozen forecasts."])
 return "\n".join(rows)+"\n"
def main():
 p=argparse.ArgumentParser()
 for a in ("snapshot","rotation","output","summary"):p.add_argument("--"+a,required=True)
 p.add_argument("--availability")
 x=p.parse_args()
 snap=json.loads(Path(x.snapshot).read_text())
 rotation=json.loads(Path(x.rotation).read_text())
 evidence=json.loads(Path(x.availability).read_text()) if x.availability else {"snapshot_sha256":snap["content_sha256"],"games":{}}
 report=build(snap,rotation,evidence)
 for path,content in ((x.output,json.dumps(report,indent=2)),(x.summary,markdown(report))):
  f=Path(path);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(content)
 print(json.dumps({"games":len(report["games"]),"allocated_teams":sum(r["allocations"] is not None for g in report["games"].values() for r in g["teams"].values())}))
if __name__=="__main__":main()
