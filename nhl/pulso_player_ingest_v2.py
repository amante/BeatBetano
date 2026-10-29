"""Import sourced NHL individual regular-season game logs for PULSO PLAYER.

NHL public web API player game-log endpoint. No scrape, no guessed records.
An explicit player manifest controls scope. Source URL and ingestion time are
recorded in a companion manifest; failures fail closed, not converted to zeroes.
"""
import argparse,csv,json,urllib.request
from datetime import date,datetime,timezone
from pathlib import Path
try:
 from nhl.pulso_player_v1 import validate,replay
except ModuleNotFoundError:
 from pulso_player_v1 import validate,replay

API="https://api-web.nhle.com/v1/player/{player}/game-log/{season}/2"
SEASONS=("20232024","20242025","20252026","20262027")
COLUMNS=("game_id","date","player_id","team","opponent","home","rest_days","toi_minutes","shots_on_goal","goals")

def fetch_json(url):
 req=urllib.request.Request(url,headers={"User-Agent":"PulsoResearch/1.0 (noncommercial historical validation)","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=35) as response:
  return json.load(response)

def to_minutes(value):
 a=str(value).split(":")
 if len(a)!=2 or not all(x.isdigit() for x in a):raise ValueError("Missing/invalid TOI")
 seconds=int(a[0])*60+int(a[1])
 if int(a[1])>=60:raise ValueError("Invalid TOI seconds")
 return seconds/60.

def normalize_player(player_id,records):
 out=[];previous=None
 for raw in sorted(records,key=lambda x:(x.get("gameDate",""),str(x.get("gameId","")))):
  d=date.fromisoformat(raw["gameDate"])
  if previous is None:
   previous=d
   continue # unknown rest since earlier season may not be present
  rest=(d-previous).days-1
  if rest<0:raise ValueError("Duplicate date / invalid prior game")
  previous=d
  side=raw.get("homeRoadFlag")
  if side not in ("H","R"):raise ValueError("Unknown home/away")
  out.append({"game_id":str(raw["gameId"]),"date":d.isoformat(),
   "player_id":str(player_id),"team":raw["teamAbbrev"],
   "opponent":raw["opponentAbbrev"],"home":side=="H",
   "rest_days":rest,"toi_minutes":to_minutes(raw["toi"]),
   "shots_on_goal":raw["shots"],"goals":raw["goals"]})
 return out

def collect(ids,seasons=SEASONS,fetch=fetch_json):
 all_rows=[];sources=[]
 for player_id in ids:
  records=[]
  for season in seasons:
   url=API.format(player=player_id,season=season)
   body=fetch(url)
   if not isinstance(body,dict) or not isinstance(body.get("gameLog"),list):
    raise ValueError("Unexpected NHL API response: "+url)
   records.extend(body["gameLog"])
   sources.append({"player_id":str(player_id),"season":season,"url":url,
                   "rows":len(body["gameLog"])})
  all_rows.extend(normalize_player(player_id,records))
 return validate(all_rows),sources

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--players",required=True,help="JSON array of NHL numeric player IDs")
 p.add_argument("--output-dir",required=True)
 p.add_argument("--start",default="2025-10-01")
 args=p.parse_args()
 ids=json.loads(Path(args.players).read_text())
 if not isinstance(ids,list) or not ids or len(ids)>1000 or len(ids)!=len(set(map(str,ids))):
  raise ValueError("Require 1-1000 distinct player IDs")
 if any(not str(x).isdigit() or int(x)<1 for x in ids):raise ValueError("Invalid player ID")
 rows,sources=collect([str(x) for x in ids])
 dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
 with (dest/"player_logs.csv").open("w",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=COLUMNS);writer.writeheader();writer.writerows(rows)
 evaluation=replay(rows,start_date=args.start)
 (dest/"player_replay.json").write_text(json.dumps(evaluation,indent=2))
 (dest/"source_manifest.json").write_text(json.dumps({
  "provider":"NHL Web API","retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
  "scope":"regular season 2023-24 through 2026-27","sources":sources,
  "normalized_rows":len(rows),"player_count":len(ids),
  "point_in_time_caveat":"historical game logs were retrieved retrospectively; only prior-date game stats are consumed by forecast; no assertion of live pregame capture"},indent=2))
 print(json.dumps({"players":len(ids),"rows":len(rows),
  "evaluated_player_games":evaluation["observations"],"scores":evaluation["scores"]},indent=2))
if __name__=="__main__":main()
