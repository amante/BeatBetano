"""Official NHL fixture audit and conservative third-party goalie status adjudication.

NHL score API confirms schedule, never prospective goalies. The provider
observations must be supplied with timestamp, source and NHL player ID.
Confirmed is a *provider assertion*, not independently verified team news.
"""
import argparse,json,re,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone
try:
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from roster_aware_units import timepoint

API="https://api-web.nhle.com/v1/score/"
def fixtures(data,day):
 games=data.get("games")
 if not isinstance(games,list):raise ValueError("Missing official NHL game list")
 out=[]
 for g in games:
  if not isinstance(g,dict) or not isinstance(g.get("id"),int):raise ValueError("Invalid NHL fixture")
  home=(g.get("homeTeam") or {}).get("abbrev");away=(g.get("awayTeam") or {}).get("abbrev")
  start=g.get("startTimeUTC")
  if not all((home,away,start)) or home==away:raise ValueError("Incomplete NHL fixture")
  out.append({"game_id":str(g["id"]),"home":home,"away":away,"scheduled_start":start,
              "game_state":g.get("gameState"),"date_requested":day})
 return out

def capture_schedule(day):
 if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day):raise ValueError("Invalid date")
 url=API+day
 with urlopen(Request(url,headers={"User-Agent":"BeatBetano-research/1.0","Accept":"application/json"}),timeout=25) as r:
  raw=r.read(2_000_000)
  if r.read(1):raise ValueError("Oversized official response")
 captured=datetime.now(timezone.utc).isoformat()
 return {"source_url":url,"captured_at":captured,"raw_sha256":hashlib.sha256(raw).hexdigest(),
         "fixtures":fixtures(json.loads(raw),day)}

def verify(schedule,game_id,observation,rosters):
 matches=[g for g in schedule["fixtures"] if g["game_id"]==str(game_id)]
 if len(matches)!=1:raise ValueError("Fixture not found uniquely")
 game=matches[0];start=timepoint(game["scheduled_start"]);s_time=timepoint(schedule["captured_at"])
 if s_time>=start:raise ValueError("Official schedule snapshot captured after puck drop")
 if game["game_state"] not in ("FUT","PRE"):raise ValueError("Not pregame state")
 if not observation.get("source_url") or not observation.get("as_of"):raise ValueError("Missing goalie source provenance")
 t=timepoint(observation["as_of"])
 if t>=start or t>s_time:raise ValueError("Goalie information not available pregame/as-of")
 if observation.get("game_id")!=game["game_id"]:raise ValueError("Goalie fixture mismatch")
 if observation.get("team") not in (game["home"],game["away"]):raise ValueError("Goalie team mismatch")
 status=observation.get("status")
 if status not in ("projected","probable","confirmed","unknown"):raise ValueError("Invalid source goalie status")
 player_id=observation.get("player_id")
 roster=next((r for r in rosters if r["team"]==observation["team"]),None)
 if not roster:raise ValueError("Current team roster missing")
 if timepoint(roster["as_of"])>t:raise ValueError("Roster timestamp later than goalie observation")
 ids={p["player_id"] for p in roster["players"] if p.get("position_group")=="goalie"}
 if status!="unknown" and (not isinstance(player_id,int) or player_id not in ids):
  raise ValueError("Goalie ID not verified in team roster")
 if status=="confirmed" and not observation.get("confirmation_evidence_url"):
  raise ValueError("Confirmation requires explicit evidence link")
 return {"fixture":game,"goalie_team":observation["team"],"goalie_player_id":player_id,
   "goalie_status":status,"goalie_status_authority":"source_asserted_not_independently_confirmed",
   "source_url":observation["source_url"],"as_of":observation["as_of"],
   "confirmed_as_official":False,"lineup_verified":False,"eligible_for_full_crs":False,
   "odds_used":False,"model_promoted":False}

def main():
 p=argparse.ArgumentParser()
 for key in ("schedule","game-id","goalie-observation","rosters","output"):p.add_argument("--"+key,required=True)
 a=p.parse_args()
 result=verify(json.loads(Path(a.schedule).read_text()),a.game_id,
   json.loads(Path(a.goalie_observation).read_text()),json.loads(Path(a.rosters).read_text()))
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 print(json.dumps({"game_id":result["fixture"]["game_id"],"goalie_status":result["goalie_status"],
                   "eligible_for_full_crs":False},indent=2))
if __name__=="__main__":main()
