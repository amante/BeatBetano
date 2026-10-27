"""Resolve NBA current-roster evidence and per-player availability without inventing active status.

Inputs are normalized, timestamped observations from external provider adapters.
Current roster membership does not establish availability. Projected starters
do not establish a complete active roster. Conflicting statuses stay unresolved.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

OUT={"out","inactive","suspended"}
IN={"available","active","probable"}
UNKNOWN={"questionable","doubtful","unknown"}
def utc(value):
 try:
  d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (TypeError,ValueError):return None

def resolve(snapshot,roster_feed,status_feed,lineups):
 digest=snapshot.get("content_sha256")
 if any(x.get("snapshot_sha256")!=digest for x in (roster_feed,status_feed,lineups)):
  raise ValueError("Source snapshot mismatch")
 output={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=utc(game["tipoff_utc"])
  teams={}
  for team in (game["home_team"],game["away_team"]):
   evidence=roster_feed.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   observed=utc(evidence.get("observed_at_utc"))
   members=evidence.get("players",[])
   good=bool(observed and tip and observed<tip and evidence.get("source_url") and evidence.get("roster_complete") is True and isinstance(members,list) and len(members)>=5)
   selected=lineups.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   starter_names=selected.get("starters",[]) if selected.get("lineup_status") in ("confirmed","projected") else []
   status_rows=status_feed.get("games",{}).get(gid,{}).get("teams",{}).get(team,[])
   statuses={}
   for row in status_rows if isinstance(status_rows,list) else []:
    pid=str(row.get("player_id") or "");time=utc(row.get("observed_at_utc"))
    if pid and time and time<tip and row.get("source_url") and row.get("status") in OUT|IN|UNKNOWN:
     statuses.setdefault(pid,[]).append(row)
   players=[];unresolved=[];seen=set()
   for member in members if good else []:
    pid=str(member.get("player_id") or "");name=member.get("player")
    if not pid or pid in seen or not name:good=False;break
    seen.add(pid)
    claims=statuses.get(pid,[])
    normalized={"out" if r["status"] in OUT else "available" if r["status"] in IN else "questionable" for r in claims}
    status=next(iter(normalized)) if len(normalized)==1 else "unknown"
    if status=="unknown" or status=="questionable":unresolved.append(pid)
    players.append({"player_id":pid,"player":name,"status":status,
      "starter_projected":name in starter_names,
      "status_sources":[{"url":r["source_url"],"status":r["status"],"observed_at_utc":r["observed_at_utc"]} for r in claims],
      "max_minutes":member.get("max_minutes",48)})
   ready=good and not unresolved and all(p["status"] in ("available","out") for p in players)
   teams[team]={"roster_complete":bool(good),"roster_source":evidence.get("source_url") if good else None,
    "observed_at_utc":evidence.get("observed_at_utc") if good else None,
    "players":players if good else [],"unresolved_player_ids":unresolved if good else [],
    "lineup_status":selected.get("lineup_status","unavailable"),"allocation_ready":bool(ready),
    "availability_source_verified":bool(ready),
    "status":"resolved" if ready else "unresolved_statuses" if good else "roster_unverified"}
  output[gid]={"teams":teams}
 return {"snapshot_sha256":digest,"games":output,"no_odds_input":True,"probabilities_adjusted":False,
  "note":"Requires explicit full roster feed and individually sourced statuses. Absence of injury mention is NOT active confirmation."}

def markdown(result):
 lines=["## NBA — Plantilla actual y disponibilidad por partido","",
 "| Partido | Equipo | Plantilla | Jugadores | Sin resolver | Apto para minutos |",
 "|---|---|---|---:|---:|---|"]
 for gid,game in result["games"].items():
  for team,data in game["teams"].items():
   lines.append(f'| {gid} | {team} | {data["status"]} | {len(data["players"])} | {len(data["unresolved_player_ids"])} | {"Sí" if data["allocation_ready"] else "No"} |')
 lines+=["","Sin lista completa y estados atribuidos no se generan minutos definitivos."]
 return "\n".join(lines)+"\n"

def main():
 ap=argparse.ArgumentParser()
 for field in ("snapshot","roster","statuses","lineups","output","summary"):ap.add_argument("--"+field,required=True)
 a=ap.parse_args();snap=json.loads(Path(a.snapshot).read_text())
 read=lambda path:json.loads(Path(path).read_text()) if Path(path).exists() else {"snapshot_sha256":snap["content_sha256"],"games":{}}
 result=resolve(snap,read(a.roster),read(a.statuses),read(a.lineups))
 for path,value in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result))):
  target=Path(path);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
 print(json.dumps({"games":len(result["games"]),"ready_teams":sum(t["allocation_ready"] for g in result["games"].values() for t in g["teams"].values())}))
if __name__=="__main__":main()
