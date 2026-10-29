"""Capture live ESPN NHL scoreboard and conservatively extract goalie observations.

The raw provider feed is the evidence. No fallback is called 'confirmed'.
Unrecognized goalie schemas produce UNKNOWN, never inferred names or starters.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

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
   candidates=[x for x in competitor.get("probables",[]) if isinstance(x,dict) and x.get("name")=="probableStartingGoalie"]
   if len(candidates)>1:raise ValueError("Ambiguous probableStartingGoalie objects")
   cand=candidates[0] if candidates else {}
   athlete=cand.get("athlete") or {}
   raw_status=cand.get("status") or {}
   explicit=raw_status.get("type") if isinstance(raw_status,dict) else raw_status
   state=str(explicit).lower() if explicit is not None else ""
   status={"confirmed":"confirmed","expected":"projected","probable":"probable","projected":"projected"}.get(state,"unknown")
   name=athlete.get("displayName") or athlete.get("fullName")
   out.append({"espn_event_id":str(ev.get("id","")),"team":abbr,
     "event_start":ev.get("date"),"home_away":competitor.get("homeAway"),
     "provider_goalie_name":name,"provider_athlete_id":athlete.get("id"),
     "goalie_status":status,"provider_raw_status":explicit,
     "nhl_player_id":None,"matchup_verified":False,
     "confirmation_evidence_url":None,
     "source_url":metadata["source_url"],"source_captured_at":metadata["retrieved_at"],
     "source_class":"ESPN scoreboard probableStartingGoalie; source assertion only",
     "eligible_for_crs":False})
 return {"source":metadata,"observations":out,
   "confirmed_goalies":sum(x["goalie_status"]=="confirmed" for x in out),
   "linked_nhl_player_ids":0,"eligible_for_crs":False,
   "notice":"Source confirmed does not mean NHL verified; cross-check roster identity, fixture and pregame timestamp."}

def reconcile(report,rosters,official_schedule):
 try:
  from nhl.roster_aware_units import timepoint
 except ModuleNotFoundError:
  from roster_aware_units import timepoint
 import unicodedata
 def norm(x):
  s=unicodedata.normalize("NFKD",str(x).casefold())
  return "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).strip()
 aliases={"NJ":"NJD","SJ":"SJS","LA":"LAK","TB":"TBL","UTAH":"UTA"}
 indexed={r["team"]:r for r in rosters}
 outcome=[]
 for row in report["observations"]:
  team=aliases.get(row["team"],row["team"])
  raw_team=row["team"]
  roster=indexed.get(team)
  errors=[]
  if not roster:errors.append("roster_missing")
  paired=[x for x in report["observations"] if x.get("espn_event_id")==row.get("espn_event_id")]
  paired_teams={aliases.get(x["team"],x["team"]) for x in paired}
  if row.get("home_away") not in ("home","away") or len(paired)!=2 or len(paired_teams)!=2:
   errors.append("espn_event_teams_incomplete")
  games=[g for g in official_schedule["fixtures"]
         if {g["home"],g["away"]}==paired_teams
         and g[row["home_away"]]==team
         and timepoint(g["scheduled_start"])==timepoint(row["event_start"])] if "espn_event_teams_incomplete" not in errors else []
   if len(games)!=1:errors.append("fixture_mismatch")
  if games and timepoint(row["source_captured_at"])>=timepoint(games[0]["scheduled_start"]):
   errors.append("source_after_start")
  if roster and timepoint(roster["as_of"])>timepoint(row["source_captured_at"]):
   errors.append("roster_after_source")
  player_id=None
  if roster and row["provider_goalie_name"]:
   matches=[p for p in roster["players"] if p.get("position_group")=="goalie" and norm(p.get("full_name"))==norm(row["provider_goalie_name"])]
   if len(matches)==1:player_id=matches[0]["player_id"]
   else:errors.append("goalie_name_unmatched_or_ambiguous")
  else:errors.append("goalie_name_missing")
  # The source might be mismatched even when ESPN calls it confirmed.
  status=row["goalie_status"]
  outcome.append({**row,"team":team,"espn_team":raw_team,"nhl_player_id":player_id,
    "nhl_game_id":games[0]["game_id"] if len(games)==1 else None,
    "matchup_verified":len(games)==1 and not any(x in errors for x in ("source_after_start","fixture_mismatch")),
    "validation_errors":errors,"source_status":status,
    "usable_pregame_identity":bool(not errors and player_id is not None and status!="unknown"),
    "eligible_for_crs":False})
 return {"observations":outcome,"resolved_goalie_ids":sum(x["nhl_player_id"] is not None for x in outcome),
  "usable_pregame_identities":sum(x["usable_pregame_identity"] for x in outcome),
  "eligible_for_crs":False,"status":"identity/fixture reconciliation only; no independently confirmed starter"}

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
