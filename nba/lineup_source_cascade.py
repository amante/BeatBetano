"""NBA lineup evidence cascade: select best pretip observation, never falsely confirm.

Source adapters provide normalized candidates with:
game_id, team, provider, source_url, observed_at_utc, status, starters.
Only actual source observations qualify. No invented lineups.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

PRIORITY={"nba_official":0,"team_official":1,"rotowire":2,"espn":3,"propedia":4,"other":5}
STATUSES={"confirmed","projected"}
def parse_time(v):
 try:
  d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,TypeError):return None
def cascade(snapshot,sources,observed_at_utc=None):
 as_of=parse_time(observed_at_utc or snapshot["created_at_utc"])
 if as_of is None:raise ValueError("UTC as_of required")
 slates={str(g["game_id"]):g for g in snapshot["predictions"]}
 result={}
 records=sources.get("candidates",[])
 if not isinstance(records,list):raise ValueError("Invalid source candidates")
 for gid,g in slates.items():
  tip=parse_time(g["tipoff_utc"])
  if tip is None:raise ValueError("UTC tipoff required")
  teams={}
  for team in (g["home_team"],g["away_team"]):
   valid=[];rejected=[]
   for r in records:
    if str(r.get("game_id"))!=gid or r.get("team")!=team:continue
    observed=parse_time(r.get("observed_at_utc"))
    players=r.get("starters")
    reason=None
    if r.get("provider") not in PRIORITY:reason="unknown_provider"
    elif r.get("status") not in STATUSES:reason="unknown_status"
    elif not observed or observed>=tip or observed>as_of:reason="not_pretip_observation"
    elif not isinstance(r.get("source_url"),str) or not r["source_url"].startswith("https://"):reason="missing_source_url"
    elif not isinstance(players,list) or len(players)!=5 or len(set(players))!=5 or any(not isinstance(x,str) or not x.strip() for x in players):reason="invalid_starting_five"
    if reason:rejected.append({"provider":r.get("provider"),"reason":reason});continue
    valid.append(r)
   # Verified status trumps projected, then source priority, then recency.
   valid.sort(key=lambda r:(r["status"]!="confirmed",PRIORITY[r["provider"]],-parse_time(r["observed_at_utc"]).timestamp()))
   chosen=valid[0] if valid else None
   teams[team]={"lineup_status":chosen["status"] if chosen else "unavailable",
    "starters":chosen["starters"] if chosen else [],
    "source_provider":chosen["provider"] if chosen else None,
    "source_url":chosen["source_url"] if chosen else None,
    "observed_at_utc":chosen["observed_at_utc"] if chosen else None,
    "candidate_count":len(valid),"rejected":rejected,
    "sources_consistent":len({tuple(sorted(x["starters"])) for x in valid})<=1 if valid else None,
    "is_official_confirmation":bool(chosen and chosen["status"]=="confirmed" and chosen["provider"] in ("nba_official","team_official")),
    "minutes_adjustment_approved":False}
  result[gid]={"home_team":g["home_team"],"away_team":g["away_team"],"teams":teams}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":result,"no_odds_input":True,
  "note":"This cascade uses normalized source observations; providers must be connected separately. Status confirmed from a third party remains attributed, not an official confirmation. Source conflicts disclosed."}
def markdown(report):
 out=["## NBA | Cascada de quintetos","",
 "Confirmado no es lo mismo que proyectado. No hay cambios automáticos de probabilidad.","",
 "| Partido | Equipo | Estado | Fuente | Candidatos | Coincidencia | Quinteto |",
 "|---|---|---|---|---:|---|---|"]
 for game in report["games"].values():
  for team,info in game["teams"].items():
   players=", ".join(info["starters"]) if info["starters"] else "—"
   out.append(f'| {game["away_team"]} @ {game["home_team"]} | {team} | {info["lineup_status"]} | {info["source_provider"] or "—"} | {info["candidate_count"]} | {info["sources_consistent"]} | {players} |')
 return "\n".join(out)+"\n"
def main():
 a=argparse.ArgumentParser()
 for key in ("snapshot","sources","output","summary"):a.add_argument("--"+key,required=True)
 args=a.parse_args()
 snap=json.loads(Path(args.snapshot).read_text());sources=json.loads(Path(args.sources).read_text())
 report=cascade(snap,sources)
 for name,content in ((args.output,json.dumps(report,indent=2)),(args.summary,markdown(report))):
  path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
 print(json.dumps({"games":len(report["games"]),"teams_with_candidates":sum(bool(x["starters"]) for game in report["games"].values() for x in game["teams"].values())}))
if __name__=="__main__":main()
