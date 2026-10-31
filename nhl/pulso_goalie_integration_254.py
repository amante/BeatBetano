"""Validated fixture-level candidate goalie observations, never starter confirmations."""
from nhl.pulso_pregame_v7 import parse_utc

def join(report, identity, goalie):
 at=parse_utc(report["generated_at_utc"])
 if goalie.get("kind")!="nhl_goalie_descriptive_daily_253" or goalie.get("official_predictions")!=0 or goalie.get("calibrated") is not False:
  raise ValueError("Uncalibrated goalie source required")
 if parse_utc(goalie["as_of_utc"])!=at or parse_utc(identity["as_of_utc"])!=at:
  raise ValueError("Capture timestamp mismatch")
 gi={str(x["game_id"]):x for x in goalie["games"]}
 ii={str(x["game_id"]):x for x in identity["games"]}
 if len(gi)!=len(goalie["games"]) or len(ii)!=len(identity["games"]) or len(gi)!=len(report["games"]):
  raise ValueError("Duplicate or missing fixtures")
 result={}
 for f in report["games"]:
  gid=str(f["game_id"]);g=gi.get(gid);i=ii.get(gid)
  if not g or not i or (g["home"],g["away"])!=(f["home"],f["away"]) or (i["home"],i["away"])!=(f["home"],f["away"]):
   raise ValueError("Fixture mismatch")
  if at>=parse_utc(f["start_utc"]):raise ValueError("Not pregame")
  result[gid]={}
  for team in (f["home"],f["away"]):
   row=g["teams"][team];source=i["teams"][team]
   if row.get("nhl_player_id")!=source.get("source_goalie_player_id"):raise ValueError("Player ID mismatch")
   if row.get("starter_status")!="not_independently_confirmed":raise ValueError("Not a candidate")
   observed=row.get("status")=="descriptive_evidence_only"
   if observed:
    for field in ("shrunk_sv_pct","season_sv_pct"):
     v=row.get(field)
     if type(v) not in (int,float) or not 0<=v<=1:raise ValueError("Invalid save rate")
   result[gid][team]={"observed":observed,"player_id":row.get("nhl_player_id"),
    "historical_metrics":{k:row.get(k) for k in ("season_sv_pct","shrunk_sv_pct","recent_5_sv_pct","season_shots_against","days_since_last_appearance")} if observed else None,
    "starter_verified":False,"probability_delta":None}
 return result
