"""#251: acquire dated NHL goalie game logs for identified candidate goalies.

Candidate identification is not starting confirmation. No odds, no ML impact.
Only games strictly before the prediction UTC calendar day enter metrics.
"""
import argparse,json,hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from nhl.pulso_pregame_v7 import parse_utc

HOST="https://api-web.nhle.com/v1/player"
def season_for(day):
 year=int(day[:4]);start=year if int(day[5:7])>=7 else year-1
 return str(start)+str(start+1)
def fetch(pid,season,timeout=15):
 if type(pid) is not int or pid<=0:raise ValueError("Invalid player ID")
 if not (len(season)==8 and season.isdigit()):raise ValueError("Bad season")
 url=f"{HOST}/{pid}/game-log/{season}/2"
 with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"BeatBetano-research/1.0"}),timeout=timeout) as response:
  raw=response.read(2000000)
  if response.read(1):raise ValueError("Oversized NHL response")
 return json.loads(raw),{"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"retrieved_at":datetime.now(timezone.utc).isoformat()}
def metrics(data,cutoff):
 rows=data.get("gameLog")
 if not isinstance(rows,list):raise ValueError("Missing official NHL gameLog")
 valid=[];bad=0
 for row in rows:
  date=row.get("gameDate")
  if not isinstance(date,str) or len(date)!=10:raise ValueError("Game missing date")
  if date>=cutoff:continue
  shots=row.get("shotsAgainst");against=row.get("goalsAgainst");saves=row.get("saves")
  # NHL web game logs commonly expose shotsAgainst + goalsAgainst + savePctg,
  # not an explicit saves field; derive saves only when both inputs are valid.
  if type(shots) is not int or shots<=0:
   bad+=1;continue
  if saves is None and type(against) is int and 0<=against<=shots:
   saves=shots-against
  if type(saves) is not int or saves<0 or saves>shots or (type(against) is int and saves+against!=shots):
   bad+=1;continue
  pct=row.get("savePctg")
  if pct is not None and (type(pct) not in (int,float) or not 0<=pct<=1 or abs(saves/shots-pct)>0.002):
   bad+=1;continue
  valid.append({"date":date,"saves":saves,"shots":shots,
    "game_id":str(row.get("gameId",""))})
 valid.sort(key=lambda x:(x["date"],x["game_id"]))
 recent=valid[-5:]
 def summarize(records):
  saves=sum(x["saves"] for x in records);shots=sum(x["shots"] for x in records)
  return {"games":len(records),"shots_against":shots,"saves":saves,
    "save_pct":round(saves/shots,6) if shots else None}
 return {"season_to_date":summarize(valid),"last_5_games":summarize(recent),
  "last_game_date":valid[-1]["date"] if valid else None,
  "excluded_bad_records":bad,"cutoff_exclusive":cutoff}
def collect(report,identity,fetcher=fetch):
 at=parse_utc(report["generated_at_utc"])
 if report.get("data_kind")!="source_readiness_only" or identity.get("kind")!="nhl_fixture_identity_gate_248":
  raise ValueError("Incorrect evidence kind")
 if parse_utc(identity["as_of_utc"])!=at:raise ValueError("Mismatched as-of")
 fixtures={str(g["game_id"]):g for g in identity["games"]}
 candidates=set()
 for f in report["games"]:
  g=fixtures.get(str(f["game_id"]))
  if not g or (g["home"],g["away"])!=(f["home"],f["away"]):raise ValueError("Fixture mismatch")
  if parse_utc(f["start_utc"])<=at:raise ValueError("Game already started")
  for team in (f["home"],f["away"]):
   pid=g["teams"][team].get("source_goalie_player_id")
   if type(pid) is int:candidates.add(pid)
 season=season_for(at.date().isoformat())
 responses={}
 def get(pid):
  try:return pid,fetcher(pid,season),None
  except (OSError,ValueError,KeyError,TypeError) as error:return pid,None,type(error).__name__
 with ThreadPoolExecutor(max_workers=5) as pool:
  for task in as_completed([pool.submit(get,pid) for pid in sorted(candidates)]):
   pid,result,error=task.result()
   if error:responses[pid]={"status":"blocked","reason":"fetch_"+error};continue
   payload,meta=result
   retrieved=parse_utc(meta["retrieved_at"])
   if retrieved<at or any(retrieved>=parse_utc(f["start_utc"]) for f in report["games"]):
    responses[pid]={"status":"blocked","reason":"source_outside_valid_pregame_window"}
    continue
   try:summary=metrics(payload,at.date().isoformat())
   except (KeyError,TypeError,ValueError) as exc:
    responses[pid]={"status":"blocked","reason":"malformed_goalie_game_log_"+type(exc).__name__};continue
   responses[pid]={"status":"observed" if summary["season_to_date"]["games"] else "no_prior_games",
    "metrics":summary,"source":meta}
 games=[]
 for f in report["games"]:
  g=fixtures[str(f["game_id"])]
  teams={}
  for team in (f["home"],f["away"]):
   pid=g["teams"][team].get("source_goalie_player_id")
   info=responses.get(pid,{"status":"blocked","reason":"no_fixture_linked_goalie"})
   teams[team]={"nhl_player_id":pid,"source_goalie_status":g["teams"][team]["source_goalie_status"],
    "independently_confirmed_starter":False,**info,"official_ml_impact":None}
  games.append({"game_id":str(f["game_id"]),"home":f["home"],"away":f["away"],"teams":teams})
 return {"kind":"nhl_candidate_goalie_history_251","as_of_utc":report["generated_at_utc"],
  "season":season,"games":games,"candidate_player_ids":len(candidates),
  "observed_team_sides":sum(t["status"]=="observed" for g in games for t in g["teams"].values()),
  "official_predictions":0,"odds_used":False,
  "limitations":["Historical candidate goalie save rates only, not GSAx or confirmed starters.",
    "Game-log HTTP capture has its own timestamp after report generation and before every fixture puck drop; it must not be backdated to original report as-of."]}
def main():
 p=argparse.ArgumentParser()
 for name in ("report","identity","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 result=collect(json.loads(Path(a.report).read_text()),json.loads(Path(a.identity).read_text()))
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 print(json.dumps({"team_sides_with_history":result["observed_team_sides"],"candidate_player_ids":result["candidate_player_ids"],"official_predictions":0}))
if __name__=="__main__":main()
