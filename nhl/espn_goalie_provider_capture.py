"""Capture live ESPN NHL scoreboard and conservatively extract goalie observations.

The raw provider feed is the evidence. No fallback is called 'confirmed'.
Unrecognized goalie schemas produce UNKNOWN, never inferred names or starters.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from nhl.pregame_fixture_goalie_verifier import fixtures

HOST="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates="
def read(day):
 if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day):raise ValueError("Invalid date")
 url=HOST+day.replace("-","")
 with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"BeatBetano-research/1.0"}),timeout=25) as r:
  raw=r.read(4_000_000)
  if r.read(1):raise ValueError("Oversized ESPN response")
 return raw,{"source_url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),
             "raw_sha256":hashlib.sha256(raw).hexdigest()}

def extract(data,metadata):
 if not isinstance(data.get("events"),list):raise ValueError("Missing events")
 out=[]
 for ev in data["events"]:
  competitions=ev.get("competitions") or []
  if len(competitions)!=1:continue
  comp=competitions[0]
  for competitor in comp.get("competitors",[]):
   team=competitor.get("team") or {}
   abbr=team.get("abbreviation")
   if not abbr:continue
   # The ESPN scoreboard goalie schema varies. Only explicit object fields
   # with unambiguous starter status are candidates for extraction.
   cand=competitor.get("probableStarter")
   if not isinstance(cand,dict):cand=None
   athlete=(cand or {}).get("athlete")
   if not isinstance(athlete,dict):athlete=cand
   name=(athlete or {}).get("displayName") if isinstance(athlete,dict) else None
   provider_id=(athlete or {}).get("id") if isinstance(athlete,dict) else None
   explicit=(cand or {}).get("status") if cand else None
   status="unknown"
   if isinstance(explicit,str):
    s=explicit.lower()
    if s in ("probable","projected","confirmed"):status=s
   # A goalie name alone is never an official goalie confirmation.
   out.append({"espn_event_id":str(ev.get("id","")),"team":abbr,
     "provider_goalie_name":name,"provider_athlete_id":provider_id,
     "goalie_status":status,"provider_raw_status":explicit,
     "nlh_player_id":None,"matchup_verified":False,
     "confirmation_evidence_url":None,
     "source_url":metadata["source_url"],"source_captured_at":metadata["retrieved_at"],
     "source_class":"ESPN scoreboard provider report, unverified",
     "eligible_for_crs":False})
 return {"source":metadata,"observations":out,"confirmed_goalies":sum(x["goalie_status"]=="confirmed" for x in out),
   "linked_nhl_player_ids":0,"eligible_for_crs":False,
   "notice":"No NHL player identity, fixture crosswalk or independent starter evidence inferred from ESPN athlete IDs."}

def main():
 p=argparse.ArgumentParser();p.add_argument("--date",required=True)
 p.add_argument("--output",required=True);p.add_argument("--raw-output",required=True)
 args=p.parse_args();raw,meta=read(args.date)
 result=extract(json.loads(raw),meta)
 path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2));Path(args.raw_output).write_bytes(raw)
 print(json.dumps({"observations":len(result["observations"]),"provider_reported_confirmed":result["confirmed_goalies"],
                    "linked_nhl_player_ids":0,"eligible_for_crs":False},indent=2))
if __name__=="__main__":main()
