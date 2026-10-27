"""Reconcile sourced projected/confirmed starting names against historical player IDs.

Diagnostic only. A five-man lineup does not establish the full active roster,
availability of bench players, or authorization to allocate 240 minutes.
"""
import argparse,json,unicodedata
from pathlib import Path

def key(name):
 return " ".join("".join(c for c in unicodedata.normalize("NFKD",name.lower()) if not unicodedata.combining(c)).split())

def reconcile(snapshot,rotation,lineups):
 digest=snapshot.get("content_sha256")
 if any(x.get("snapshot_sha256")!=digest for x in (rotation,lineups)):raise ValueError("Snapshot mismatch")
 result={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);teams={}
  for team in (game["home_team"],game["away_team"]):
   current=lineups.get("games",{}).get(gid,{}).get("teams",{}).get(team,{})
   historical=rotation.get("games",{}).get(gid,{}).get("teams",{}).get(team,{}).get("provisional_rotation",[])
   index={}
   for p in historical:
    index.setdefault(key(p.get("player") or ""),[]).append(p)
   matched=[];unmatched=[];ambiguous=[]
   starters=current.get("starters",[])
   for name in starters:
    options=index.get(key(name),[])
    if len(options)==1:
     p=options[0]
     matched.append({"player":name,"player_id":p["player_id"],"historical_minutes":p.get("minutes_projection")})
    elif not options:unmatched.append(name)
    else:ambiguous.append(name)
   teams[team]={"lineup_status":current.get("lineup_status","unavailable"),
    "source_provider":current.get("source_provider"),
    "observed_at_utc":current.get("observed_at_utc"),
    "starters_reported":len(starters),"matched_starters":matched,
    "unmatched_starters":unmatched,"ambiguous_starters":ambiguous,
    "full_current_roster_verified":False,"bench_availability_verified":False,
    "allocation_ready":False,
    "why_not_ready":"Projected/confirmed starters alone do not verify entire eligible roster and injuries"}
  result[gid]={"home_team":game["home_team"],"away_team":game["away_team"],"teams":teams}
 return {"snapshot_sha256":digest,"games":result,"production_adjustment_authorized":False}
def markdown(report):
 out=["## NBA — Matching de quintetos y jugadores históricos","",
 "| Partido | Equipo | Estado quinteto | Titulares fuente | IDs vinculados | Pendientes |",
 "|---|---|---|---:|---:|---:|"]
 for g in report["games"].values():
  for team,r in g["teams"].items():
   out.append(f'| {g["away_team"]} @ {g["home_team"]} | {team} | {r["lineup_status"]} | {r["starters_reported"]} | {len(r["matched_starters"])} | {len(r["unmatched_starters"])+len(r["ambiguous_starters"])} |')
 out+=["","**Nota:** No se asignan 240 minutos hasta verificar todos los jugadores elegibles, incluidos suplentes y descartados."]
 return "\n".join(out)+"\n"
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","rotation","lineups","output","summary"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 read=lambda name:json.loads(Path(getattr(a,name)).read_text())
 r=reconcile(read("snapshot"),read("rotation"),read("lineups"))
 for name,data in ((a.output,json.dumps(r,indent=2)),(a.summary,markdown(r))):
  path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
 print(json.dumps({"games":len(r["games"]),"matched_starters":sum(len(t["matched_starters"]) for g in r["games"].values() for t in g["teams"].values())}))
if __name__=="__main__":main()
