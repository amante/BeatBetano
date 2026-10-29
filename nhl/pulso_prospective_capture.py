"""Prospective NHL source collector for PULSO: immutable as-of evidence, no picks.

Use NHL official score API for fixtures and ESPN public NHL scoreboard for
provider-asserted goalie observations. Never infer confirmed goalie from roster.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from nhl.official_roster_snapshot import fetch as fetch_roster
from nhl.nhlcom_projected_lineup_capture import capture as capture_editorial_lineups
from nhl.goalie_pregame_crosswalk import summarize as crosswalk_goalies
from nhl.pregame_fixture_goalie_verifier import capture_schedule
from nhl.espn_goalie_provider_capture import read as read_espn,extract as extract_espn
from nhl.pulso_pregame_v7 import parse_utc

def assemble(schedule,espn_observations,at=None):
 if not isinstance(espn_observations,list) or any(not isinstance(row,dict) for row in espn_observations):
  raise ValueError("Expected the ESPN observations list, not the complete report")
 now=parse_utc(at) if at else datetime.now(timezone.utc)
 output=[]
 for f in schedule["fixtures"]:
  start=parse_utc(f["scheduled_start"])
  if start<=now or f["game_state"] not in ("FUT","PRE"):continue
  matching={}
  for team in (f["home"],f["away"]):
   candidates=[g for g in espn_observations if g.get("team")==team and g.get("event_start") and
    abs((parse_utc(g["event_start"])-start).total_seconds())<=3600]
   matching[team]=candidates
  statuses={}
  blockers=["roster_snapshot_not_connected","goalie_identity_and_confirmation_not_verified",
            "team_rate_model_not_calibrated"]
  for team,rows in matching.items():
   statuses[team]={"status":"unknown","source_count":len(rows)}
   if len(rows)==1:
    statuses[team]["status"]=rows[0].get("goalie_status","unknown")
    statuses[team]["provider_goalie_name"]=rows[0].get("provider_goalie_name")
    # Provider assertion is not independently verified source confirmation.
    statuses[team]["confirmed_as_official"]=False
  output.append({"sport":"nhl","game_id":f["game_id"],"home":f["home"],"away":f["away"],
    "start_utc":f["scheduled_start"],"status":"unavailable","probabilities":None,
    "readiness_issues":blockers,"goalie_provider_observations":statuses,
    "odds_used_in_model":False,"official":False})
 return output

def capture_rosters(schedule,at=None,fetch=fetch_roster):
 """Current official roster identities; never game lineup confirmations."""
 now=parse_utc(at) if at else datetime.now(timezone.utc)
 teams=sorted({team for g in schedule["fixtures"] if parse_utc(g["scheduled_start"])>now and g["game_state"] in ("FUT","PRE") for team in (g["home"],g["away"])})
 rosters=[];failures={}
 with ThreadPoolExecutor(max_workers=6) as pool:
  tasks={pool.submit(fetch,team):team for team in teams}
  for future in as_completed(tasks):
   team=tasks[future]
   try:
    record=future.result()
    if record.get("team")!=team or parse_utc(record["as_of"])>datetime.now(timezone.utc):raise ValueError("Invalid roster identity or timestamp")
    rosters.append(record)
   except Exception as exc:
    failures[team]=type(exc).__name__+": "+str(exc)[:160]
 return sorted(rosters,key=lambda r:r["team"]),failures

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--date",required=True,help="NHL official schedule day YYYY-MM-DD")
 p.add_argument("--output-dir",required=True)
 p.add_argument("--public-status",help="Optional GitHub Pages state JSON path")
 args=p.parse_args()
 schedule=capture_schedule(args.date)
 # Freeze NHL roster snapshots before the ESPN goalie read, as required by
 # the crosswalk's point-in-time source-ordering checks.
 rosters,roster_errors=capture_rosters(schedule)
 raw,metadata=read_espn(args.date)
 espn_report=extract_espn(json.loads(raw),metadata)
 observations=espn_report["observations"]
 goalie_identity=crosswalk_goalies(espn_report,schedule,rosters)
 # NHL.com editorial lines are observations only, not game-verified starters.
 editorial=None;editorial_error=None
 try:
  _,editorial=capture_editorial_lineups()
 except (OSError,ValueError,UnicodeError) as exc:
  editorial_error=type(exc).__name__+': '+str(exc)[:160]
 captured=datetime.now(timezone.utc).isoformat()
 if parse_utc(schedule["captured_at"])>parse_utc(captured):raise ValueError("Schedule captured in future")
 # Only forthcoming fixtures are reported; never mark past games as pregame.
 games=assemble(schedule,observations,captured)
 output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
 (output/"schedule_evidence.json").write_text(json.dumps(schedule,indent=2))
 (output/"goalie_observations.json").write_text(json.dumps(espn_report,indent=2))
 (output/"official_roster_candidates.json").write_text(json.dumps({"rosters":rosters,"errors":roster_errors,"game_lineups_confirmed":0},indent=2))
 (output/"goalie_identity_crosswalk.json").write_text(json.dumps(goalie_identity,indent=2))
 (output/"editorial_lineup_observations.json").write_text(json.dumps({'observation':editorial,'fetch_error':editorial_error,'fixture_attested':False,'lineup_confirmed':False},indent=2))
 (output/"espn_raw_sha256.txt").write_text(hashlib.sha256(raw).hexdigest()+"\n")
 report={"generated_at_utc":captured,"date":args.date,"data_kind":"source_readiness_only",
  "game_count":len(games),"games":games,"official_predictions":0,
  "goalie_identity_audit":goalie_identity["summary"],"official_roster_teams_captured":len(rosters),
  "roster_capture_errors":roster_errors,
  "nhlcom_editorial_lineup_blocks":len(editorial['blocks']) if editorial else 0,
  "nhlcom_editorial_source_error":editorial_error,
  "limitations":["NHL official schedule is not a player lineup or goalie confirmation.","ESPN assertions are provider observations, not independently verified starting-goalie declarations.","No trained team goal rate is used; all game probabilities remain unavailable."]}
 (output/"report.json").write_text(json.dumps(report,indent=2))
 if args.public_status:
  path=Path(args.public_status);path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(report,indent=2))
 print(json.dumps({"date":args.date,"future_games":len(games),"official_roster_teams":len(rosters),
  "goalie_identity_audit":goalie_identity["summary"],"official_predictions":0},indent=2))
if __name__=="__main__":main()
