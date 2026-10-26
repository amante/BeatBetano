"""Conservative NBA multifeed player observation de-duplication and conflict audit.

Only structured ESPN records with explicit team and player are reconciled;
Bleacher Report editorial headlines are not independently mapped to athletes.
"""
import argparse,json,re
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

def norm(s):
 return re.sub(r"[^a-z0-9]","",str(s).casefold())
def time(s):
 d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Naive timestamp")
 return d.astimezone(timezone.utc)
def reconcile(snapshot,evidence):
 if snapshot.get("content_sha256")!=evidence.get("snapshot_sha256"):
  raise ValueError("Mismatched source snapshot")
 out={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=time(game["tipoff_utc"])
  record=evidence.get("games",{}).get(gid,{})
  allowed={game["home_team"],game["away_team"]}
  observations=defaultdict(list)
  for item in record.get("espn_injury_observations",[]):
   if not isinstance(item,dict):continue
   team=item.get("team");player=item.get("player")
   if team not in allowed or not player or not norm(player):continue
   # Only ESPN structured observations, not alleged independent confirmation.
   observations[(team,norm(player))].append({"player":player,"team":team,
      "status":str(item.get("status") or "").strip().casefold(),
      "source":"ESPN","official":False})
  reconciled=[];conflicts=0;duplicates=0
  for (_, _),items in sorted(observations.items()):
   statuses=sorted({v["status"] for v in items if v["status"]})
   duplicates+=max(0,len(items)-1)
   conflict=len(statuses)>1
   conflicts+=int(conflict)
   reconciled.append({"player":items[0]["player"],"team":items[0]["team"],
     "reported_statuses":statuses,"observations":len(items),
     "conflicting_statuses":conflict,"confirmed_official":False,
     "independent_source_count":0,"availability_for_model":None})
  alerts=[x for x in record.get("bleacher_report_headline_alerts",[])
    if isinstance(x,dict) and x.get("published_at_utc") and x.get("collected_at_utc")
    and time(x["published_at_utc"])<=time(x["collected_at_utc"])<tip]
  out[gid]={"home_team":game["home_team"],"away_team":game["away_team"],
    "unique_structured_players":len(reconciled),"duplicate_espn_records":duplicates,
    "conflicting_espn_statuses":conflicts,"players":reconciled,
    "editorial_alerts_not_player_matched":len(alerts),
    "starter_confirmations":0,"final_probabilities_authorized":False}
 return {"sport":"nba","snapshot_sha256":snapshot["content_sha256"],"games":out,
   "note":"Deduplication is not independent corroboration; editorial alerts are unassigned and may repeat ESPN."}
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","multisource","output"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 load=lambda f:json.loads(Path(f).read_text())
 r=reconcile(load(a.snapshot),load(a.multisource))
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(r,indent=2))
 print(json.dumps({"games":len(r["games"]),"players":sum(g["unique_structured_players"] for g in r["games"].values()),
 "conflicts":sum(g["conflicting_espn_statuses"] for g in r["games"].values())}))
if __name__=="__main__":main()
