"""PULSO v6+v7: point-in-time audit and conservative pregame NHL roster gate.

Predictions are never made from retrospective played-game participation. Expected
player identities must be supplied by an externally sourced as-of snapshot.
"""
import argparse,csv,json,math
from collections import defaultdict
from datetime import datetime,date,timezone
from pathlib import Path
from nhl.pulso_player_v1 import forecast,validate

STATUSES={"confirmed","probable","questionable","out","unknown"}
def parse_utc(value):
 if not isinstance(value,str):raise ValueError("Missing timestamp")
 d=datetime.fromisoformat(value.replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timestamp must include timezone")
 return d.astimezone(timezone.utc)
def audit_snapshot(snapshot,game_start_utc):
 """Return eligibility and missing evidence, never assume a roster is confirmed."""
 if not isinstance(snapshot,dict):raise ValueError("Snapshot must be an object")
 cutoff=parse_utc(game_start_utc)
 asof=parse_utc(snapshot.get("asof_utc"))
 if asof>=cutoff:raise ValueError("Availability snapshot must precede puck drop")
 if not snapshot.get("source_url") or not str(snapshot["source_url"]).startswith("https://"):
  raise ValueError("Source URL required")
 if not snapshot.get("game_id") or not snapshot.get("home_team") or not snapshot.get("away_team"):
  raise ValueError("Fixture identifier and teams required")
 roster=snapshot.get("players")
 if not isinstance(roster,list) or not roster:raise ValueError("Missing sourced roster")
 seen=set();issues=[];usable=[]
 for player in roster:
  if not isinstance(player,dict):raise ValueError("Invalid player")
  pid=str(player.get("player_id",""))
  team=player.get("team")
  key=(team,pid)
  if not pid.isdigit() or not team or key in seen:raise ValueError("Invalid or duplicate player")
  seen.add(key)
  if team not in (snapshot["home_team"],snapshot["away_team"]):raise ValueError("Unknown fixture team")
  status=player.get("status","unknown")
  if status not in STATUSES:raise ValueError("Unknown availability status")
  if status in ("out","unknown","questionable"):
   issues.append({"player_id":pid,"team":team,"status":status})
  else:usable.append(player)
 # A valid sourced probable roster is not a confirmed complete lineup.
 team_counts={team:sum(p.get("team")==team and p.get("status") in ("confirmed","probable") for p in roster) for team in (snapshot["home_team"],snapshot["away_team"])}
 if any(n<12 for n in team_counts.values()):issues.append({"kind":"insufficient_skater_coverage","counts":team_counts})
 return {"snapshot_asof":asof.isoformat(),"game_id":str(snapshot["game_id"]),
  "eligible_for_research":bool(usable),
  "eligible_for_full_team_prediction":not issues and all(n>=12 for n in team_counts.values()),
  "usable_players":usable,"issues":issues,"source_url":snapshot["source_url"]}
def project_players(history,snapshot,game_start_utc,rest_by_team):
 audit=audit_snapshot(snapshot,game_start_utc)
 day=parse_utc(game_start_utc).date().isoformat()
 if snapshot.get("game_date_local"):
  day=str(snapshot["game_date_local"])
  date.fromisoformat(day)
 if not isinstance(rest_by_team,dict):raise ValueError("Known fixture rest required")
 outputs=[]
 for player in audit["usable_players"]:
  team=player["team"];opponent=snapshot["away_team"] if team==snapshot["home_team"] else snapshot["home_team"]
  rest=rest_by_team.get(team)
  if not isinstance(rest,int) or rest<0:raise ValueError("Unknown team rest; cannot forecast")
  f=forecast(history,{"player_id":str(player["player_id"]),"team":team,"opponent":opponent,
      "home":team==snapshot["home_team"],"rest_days":rest},day)
  outputs.append({"player_id":str(player["player_id"]),"team":team,"availability":player["status"],
    "forecast":f,"source_url":audit["source_url"],"asof_utc":audit["snapshot_asof"]})
 return {"status":"research_only_no_collective_ml","snapshot_audit":{k:v for k,v in audit.items() if k!="usable_players"},
   "player_predictions":outputs,"forecast_day":day}
def audit_dated_predictions(rows):
 """Detect obvious post-date timestamps and duplicate research prediction keys."""
 seen=set();errors=[]
 for r in rows:
  key=(str(r.get("game_id")),str(r.get("player_id")))
  if key in seen:errors.append({"key":key,"error":"duplicate_prediction"})
  seen.add(key)
  if "cutoff_utc" in r and "source_asof_utc" in r:
   if parse_utc(r["source_asof_utc"])>=parse_utc(r["cutoff_utc"]):
    errors.append({"key":key,"error":"source_not_pregame"})
 return {"rows":len(rows),"errors":errors,"point_in_time_source_audited":sum("source_asof_utc" in r and "cutoff_utc" in r for r in rows),
 "limitation":"A dated historical log alone cannot prove point-in-time publication or roster availability."}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--snapshot",required=True)
 p.add_argument("--logs",required=True)
 p.add_argument("--rest",required=True,help="JSON mapping of team to known pregame rest")
 p.add_argument("--game-start-utc",required=True)
 p.add_argument("--out",required=True)
 a=p.parse_args()
 snapshot=json.loads(Path(a.snapshot).read_text())
 history=validate(list(csv.DictReader(Path(a.logs).open(newline=""))))
 result=project_players(history,snapshot,a.game_start_utc,json.loads(Path(a.rest).read_text()))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"status":result["status"],"players":len(result["player_predictions"]),
  "eligible_for_full_team_prediction":result["snapshot_audit"]["eligible_for_full_team_prediction"]},indent=2))
if __name__=="__main__":main()
