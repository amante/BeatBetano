"""Fetch current NBA roster IDs from ESPN, without inferring game availability.

Roster = membership evidence only, NOT active list. Provider failures remain
explicit and no player is assumed to be healthy or eligible for minutes.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import requests

BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
def extract_teams(payload):
 groups=payload.get("sports",[])
 teams={}
 for sport in groups:
  for league in sport.get("leagues",[]):
   for row in league.get("teams",[]):
    t=row.get("team",row)
    if t.get("abbreviation") and t.get("id"):
     teams[t["abbreviation"]]=str(t["id"])
 return teams
def extract_roster(payload):
 athletes=payload.get("athletes",[])
 if not isinstance(athletes,list):raise ValueError("Missing roster athletes")
 roster=[]
 for entry in athletes:
  items=entry.get("items") if isinstance(entry,dict) else None
  for p in items if isinstance(items,list) else [entry]:
   if not isinstance(p,dict):continue
   pid=p.get("id");name=p.get("displayName")
   if pid and name:roster.append({"player_id":str(pid),"player":str(name)})
 if len({p["player_id"] for p in roster})!=len(roster):
  raise ValueError("Duplicate player ID in roster")
 return roster
def collect(snapshot,session=None,observed=None):
 now=observed or datetime.now(timezone.utc).isoformat()
 req=session or requests.Session()
 errors=[];teams={}
 needed={t for g in snapshot["predictions"] for t in (g["home_team"],g["away_team"])}
 try:
  resp=req.get(BASE+"/teams",params={"limit":100},timeout=20)
  resp.raise_for_status()
  lookup=extract_teams(resp.json())
 except (requests.RequestException,ValueError,TypeError) as exc:
  lookup={};errors.append({"scope":"teams","error":type(exc).__name__})
 for name in sorted(needed):
  teamid=lookup.get(name)
  if not teamid:
   teams[name]={"roster_complete":False,"players":[],"status":"team_id_unresolved"}
   continue
  url=BASE+"/teams/"+teamid+"/roster"
  try:
   res=req.get(url,timeout=20);res.raise_for_status()
   members=extract_roster(res.json())
   # A plausible 5+ roster is a snapshot, but never an active gameday list.
   plausible=len(members)>=5
   teams[name]={"roster_complete":plausible,"players":members if plausible else [],
     "observed_at_utc":now,"source_url":url,"status":"roster_retrieved_not_game_availability" if plausible else "roster_incomplete"}
  except (requests.RequestException,ValueError,TypeError) as exc:
   teams[name]={"roster_complete":False,"players":[],"status":"retrieval_failed"}
   errors.append({"team":name,"error":type(exc).__name__})
 return {"snapshot_sha256":snapshot["content_sha256"],
  "games":{str(g["game_id"]):{"teams":{t:teams[t] for t in (g["home_team"],g["away_team"])}} for g in snapshot["predictions"]},
  "errors":errors,"source":"ESPN current roster; membership only; never gameday availability",
  "status_feed_produced":False,"no_odds_input":True}
def main():
 a=argparse.ArgumentParser()
 for arg in ("snapshot","output"):a.add_argument("--"+arg,required=True)
 x=a.parse_args()
 r=collect(json.loads(Path(x.snapshot).read_text()))
 f=Path(x.output);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(r,indent=2))
 print(json.dumps({"teams":len({t for g in r["games"].values() for t in g["teams"]}),
  "rosters_retrieved":len({t for g in r["games"].values() for t,v in g["teams"].items() if v["roster_complete"]}),
  "errors":len(r["errors"])}))
if __name__=="__main__":main()
