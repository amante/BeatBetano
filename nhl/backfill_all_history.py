"""Single-run historical backfill with bounded retries, checkpoints and integrity checks."""
import argparse,json,time,os
from pathlib import Path
from historical_game_collector import fetch,extract
import requests

def backfill(ledger,root,max_seconds=19000,pause=1.5):
    root.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    deadline=time.monotonic()+max_seconds
    errors=[];new=0;cached=0
    for game in sorted(ledger,key=lambda g:(g["date"],str(g["id"]))):
        gid=str(game["id"]);path=root/(gid+".json")
        if path.exists():
            try:
                item=json.loads(path.read_text())
                if (str(item.get("game_id"))==gid and item.get("date")==game["date"] and
                    item.get("goal_events_available") and item.get("boxscore",{}).get("player_by_game_stats")):
                    cached+=1;continue
            except (OSError,ValueError):pass
        if time.monotonic()+90>deadline:break
        try:
            box=fetch(session,f"https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore")
            time.sleep(pause)
            pbp=fetch(session,f"https://api-web.nhle.com/v1/gamecenter/{gid}/play-by-play")
            item=extract(game,box,pbp)
            if not item["goal_events_available"] or not item["boxscore"]["player_by_game_stats"]:
                raise ValueError("Missing event or player stats")
            tmp=path.with_suffix(".tmp")
            tmp.write_text(json.dumps(item,separators=(",",":")))
            os.replace(tmp,path);new+=1
            time.sleep(pause)
        except (requests.RequestException,ValueError,KeyError) as exc:
            errors.append({"id":gid,"error":str(exc)[:160]})
            if len(errors)>=20:break
        if new and new%100==0:
            print(f"Checkpoint: {new} new records, {cached} cached",flush=True)
    complete=sum(1 for g in ledger if (root/(str(g["id"])+".json")).is_file())
    result={"ledger_count":len(ledger),"cached_validated":cached,"newly_fetched":new,
      "file_count":complete,"remaining":len(ledger)-complete,"errors":errors,
      "complete":complete==len(ledger) and not errors,
      "status":"POSTGAME_DATA_NOT_POINT_IN_TIME_PREGAME"}
    (root/"manifest.json").write_text(json.dumps(result,indent=2))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--archive",required=True)
    p.add_argument("--max-seconds",type=int,default=19000)
    args=p.parse_args()
    result=backfill(json.loads(Path(args.history).read_text()),Path(args.archive),args.max_seconds)
    print(json.dumps(result),flush=True)
    if not result["complete"]:raise SystemExit("Incomplete run; checkpoint artifact must be resumed, not treated as full coverage")
if __name__=="__main__":main()
