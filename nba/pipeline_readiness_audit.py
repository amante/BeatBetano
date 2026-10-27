"""Read-only per-game evidence readiness: operational coverage is not predictive validation."""
import argparse,json
from pathlib import Path

def audit(snapshot,rosters,availability,minutes):
 digest=snapshot["content_sha256"]
 for label,data in (("roster",rosters),("availability",availability),("minutes",minutes)):
  if data.get("snapshot_sha256")!=digest:raise ValueError(label+" snapshot mismatch")
 games={}
 for g in snapshot["predictions"]:
  gid=str(g["game_id"]);teams={}
  for team in (g["home_team"],g["away_team"]):
   roster=rosters.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   active=availability.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   allocated=minutes.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   assigned=allocated.get("allocations")
   total=sum(assigned.values()) if isinstance(assigned,dict) else None
   complete=active.get("roster_complete") is True
   resolved=active.get("allocation_ready") is True
   valid=bool(resolved and total is not None and abs(total-240)<0.001)
   teams[team]={"roster_players":len(roster.get("players",[])),"roster_retrieved":roster.get("roster_complete") is True,
    "availability_resolved":resolved,"unresolved_players":len(active.get("unresolved_player_ids",[])),
    "minute_allocation_status":allocated.get("status","unavailable"),"minutes_total":round(total,5) if total is not None else None,
    "rotation_ready":valid,
    "missing":[name for name,ok in (("current_roster",complete),("complete_individual_availability",resolved),("feasible_240_minutes",valid)) if not ok]}
  games[gid]={"home_team":g["home_team"],"away_team":g["away_team"],"teams":teams,
   "both_teams_rotation_ready":all(t["rotation_ready"] for t in teams.values())}
 return {"snapshot_sha256":digest,"games":games,"complete_rotation_games":sum(g["both_teams_rotation_ready"] for g in games.values()),
 "pregame_probability_adjustment_authorized":False,"predictive_validation_status":"not_evaluated",
 "note":"Evidence coverage only: no comparison of predictions against actual results."}
def markdown(report):
 lines=["## NBA — Auditoría operativa por partido","",
 "| Partido | Equipo | Plantilla recuperada | Disponibilidad resuelta | Minutos | Faltantes |",
 "|---|---|---|---|---:|---|"]
 for gid,g in report["games"].items():
  for team,t in g["teams"].items():
   lines.append(f'| {gid} | {team} | {"Sí" if t["roster_retrieved"] else "No"} | {"Sí" if t["availability_resolved"] else "No"} | {t["minutes_total"] if t["minutes_total"] is not None else "—"} | {", ".join(t["missing"]) or "—"} |')
 lines+=["",f'**Partidos con ambas rotaciones completas:** {report["complete_rotation_games"]} de {len(report["games"])}.',"",
 "Esto NO demuestra precisión predictiva; no autoriza ajustes de probabilidades."]
 return "\n".join(lines)+"\n"
def main():
 p=argparse.ArgumentParser()
 for n in ("snapshot","roster","availability","minutes","output","summary"):p.add_argument("--"+n,required=True)
 a=p.parse_args();read=lambda n:json.loads(Path(getattr(a,n)).read_text())
 result=audit(read("snapshot"),read("roster"),read("availability"),read("minutes"))
 for name,value in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result))):
  f=Path(name);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value)
 print(json.dumps({"games":len(result["games"]),"complete_rotation_games":result["complete_rotation_games"]}))
if __name__=="__main__":main()
