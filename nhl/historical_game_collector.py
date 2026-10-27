"""Resumeable NHL historical boxscore/play-by-play collector.

Batch from locally persisted official game ledger, never infer pregame starters
from postgame records. Completed-game labels are research targets only.
"""
import argparse,json,time,random,os
from pathlib import Path
import requests

BASE="https://api-web.nhle.com/v1/gamecenter/{}/{}"
def fetch(session,url,sleep=time.sleep):
    for attempt in range(6):
        try:
            r=session.get(url,timeout=35)
            if r.status_code in (429,500,502,503,504):
                if attempt==5:r.raise_for_status()
                try:delay=float(r.headers.get("Retry-After",""))
                except (TypeError,ValueError):delay=min(100,3*2**attempt)
                sleep(max(2,min(120,delay)))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt==5:raise
            sleep(min(100,3*2**attempt))
    raise RuntimeError("NHL retries exhausted")

def extract(game,box,pbp):
    events=pbp.get("plays",[])
    if not isinstance(events,list):raise ValueError("Missing PBP plays")
    goals=[]
    for e in events:
        if e.get("typeDescKey")!="goal":continue
        d=e.get("details") or {}
        side=d.get("eventOwnerTeamId")
        goals.append({"event_id":e.get("eventId"),"period":(e.get("periodDescriptor") or {}).get("number"),
                      "period_type":(e.get("periodDescriptor") or {}).get("periodType"),
                      "time_in_period":e.get("timeInPeriod"),"owner_team_id":side,
                      "home_score":e.get("homeScore"),"away_score":e.get("awayScore")})
    return {"game_id":game["id"],"date":game["date"],"home":game["home"],"away":game["away"],
      "result_final":{"home_goals":game["hg"],"away_goals":game["ag"]},
      "game_info":{"game_state":box.get("gameState"),"game_type":box.get("gameType")},
      "boxscore":{"home_team":box.get("homeTeam"),"away_team":box.get("awayTeam"),
        "player_by_game_stats":box.get("playerByGameStats")},
      "goal_events":goals,"goal_events_available":bool(goals),
      "pbp_event_count":len(events),
      "point_in_time_warning":"Boxscore and PBP are POSTGAME only; never treat starting goalie or lineups as pregame confirmed."}

def run(ledger,output,max_games,delay):
    output.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    errors=[];done=0;cached=0
    for game in sorted(ledger,key=lambda g:(g["date"],g["id"])):
        if done>=max_games:break
        path=output/(str(game["id"])+".json")
        if path.is_file():
            try:
                old=json.loads(path.read_text())
                if old.get("game_id")==game["id"] and old.get("goal_events_available") and old.get("boxscore",{}).get("player_by_game_stats"):
                    cached+=1;continue
            except (ValueError,KeyError):pass
        try:
            box=fetch(session,BASE.format(game["id"],"boxscore"))
            time.sleep(delay)
            pbp=fetch(session,BASE.format(game["id"],"play-by-play"))
            parsed=extract(game,box,pbp)
            if not parsed["goal_events_available"] or not parsed["boxscore"]["player_by_game_stats"]:
                raise ValueError("Missing goal events or player stats; not cacheable")
            tmp=path.with_suffix(".tmp")
            tmp.write_text(json.dumps(parsed,separators=(",",":")))
            os.replace(tmp,path)
            done+=1
            time.sleep(delay)
        except (requests.RequestException,ValueError,KeyError) as e:
            errors.append({"game_id":game["id"],"reason":str(e)[:160]})
    result={"total_games":len(ledger),"newly_fetched":done,"cached":cached,
      "errors":errors,"remaining_estimate":max(0,len(ledger)-cached-done),
      "data_status":"postgame_labels_only_not_pregame_features"}
    (output/"manifest.json").write_text(json.dumps(result,indent=2))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--output-dir",required=True)
    p.add_argument("--max-games",type=int,default=30);p.add_argument("--delay",type=float,default=1.5)
    args=p.parse_args()
    if not 1<=args.max_games<=200:raise ValueError("max-games must be 1..200")
    if args.delay<.5:raise ValueError("Delay must be >=0.5 seconds")
    result=run(json.loads(Path(args.history).read_text()),Path(args.output_dir),args.max_games,args.delay)
    print(json.dumps(result))
    if result["errors"]:print("Partial retrieval; see manifest, no validated metrics claimed")
if __name__=="__main__":main()
