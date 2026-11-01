"""NHL #265: provenance-preserving NHL historical boxscore acquisition.

Captures source evidence, not inferred starters or calibrated forecasts. A goalie
is a verified starter ONLY when the source explicitly marks starter=True.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

HOST="https://api-web.nhle.com/v1/gamecenter"

def fetch(game_id,timeout=15):
    if not str(game_id).isdigit():
        raise ValueError("Invalid NHL game ID")
    url=f"{HOST}/{game_id}/boxscore"
    with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"BeatBetano-research/1.0"}),timeout=timeout) as response:
        payload=response.read(2000000)
        if response.read(1):
            raise ValueError("Oversized official response")
    return json.loads(payload),{"url":url,"sha256":hashlib.sha256(payload).hexdigest(),
                                "retrieved_at_utc":datetime.now(timezone.utc).isoformat()}

def extract(label,boxscore,source):
    """Never guess starter from minutes, saves, goalie list order or score."""
    gid=str(label["game_id"])
    if str(boxscore.get("id"))!=gid:
        raise ValueError("Game ID mismatch")
    if boxscore.get("gameDate")!=label["date"]:
        raise ValueError("Game date mismatch")
    stats=boxscore.get("playerByGameStats")
    if not isinstance(stats,dict):
        raise ValueError("Missing official player statistics")
    teams={}
    for side in ("home","away"):
        entry=stats.get(side+"Team")
        if not isinstance(entry,dict):
            raise ValueError("Missing team goalie details")
        rows=entry.get("goalies")
        if not isinstance(rows,list):
            raise ValueError("Missing goalie observations")
        observed=[]
        for goalie in rows:
            pid=goalie.get("playerId")
            if type(pid) is not int or pid<=0:
                raise ValueError("Invalid NHL goalie ID")
            # Only accept a source-provided explicit starter flag.
            starter=goalie.get("starter")
            if type(starter) is not bool:
                starter=None
            observed.append({"player_id":pid,"explicit_starter":starter,
                             "source_row":goalie})
        if len({p["player_id"] for p in observed})!=len(observed):
            raise ValueError("Duplicate goalie")
        confirmed=[p["player_id"] for p in observed if p["explicit_starter"] is True]
        teams[side]={"goalies":observed,
                     "starter_id":confirmed[0] if len(confirmed)==1 else None,
                     "starter_status":"source_explicit" if len(confirmed)==1 else "blocked_no_unique_explicit_starter"}
    return {"game_id":gid,"date":label["date"],"home":label["home"],"away":label["away"],
            "teams":teams,"source":source,"odds_used":False,
            "verified_starters":all(t["starter_id"] is not None for t in teams.values())}

def capture(labels,out_dir,fetcher=fetch,max_games=None):
    destination=Path(out_dir);destination.mkdir(parents=True,exist_ok=True)
    if max_games is not None and max_games<1:
        raise ValueError("Invalid limit")
    seen=set();coverage=[]
    for label in labels[:max_games]:
        gid=str(label["game_id"])
        if gid in seen:raise ValueError("Duplicate labels")
        seen.add(gid)
        path=destination/(gid+".json")
        if path.exists():
            # Existing immutable record: do not silently overwrite evidence.
            record=json.loads(path.read_text())
            if record.get("game_id")!=gid or record.get("date")!=label["date"]:
                raise ValueError("Cached record conflicts with fixture")
            coverage.append({"game_id":gid,"status":"cached","verified_starters":record["verified_starters"]})
            continue
        try:
            box,source=fetcher(gid)
            record=extract(label,box,source)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            coverage.append({"game_id":gid,"status":"blocked_"+type(exc).__name__,"verified_starters":False})
            continue
        path.write_text(json.dumps(record,indent=2))
        coverage.append({"game_id":gid,"status":"captured","verified_starters":record["verified_starters"]})
    return {"kind":"nhl_historical_boxscore_capture_265","records":coverage,
            "attempted":len(coverage),"with_explicit_starters":sum(x["verified_starters"] for x in coverage),
            "official_predictions":0,"odds_used":False,"calibrated":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True)
    p.add_argument("--out-dir",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--max-games",type=int)
    args=p.parse_args()
    with Path(args.labels).open(newline="") as handle:
        labels=list(csv.DictReader(handle))
    summary=capture(labels,args.out_dir,max_games=args.max_games)
    Path(args.manifest).write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:summary[k] for k in ("attempted","with_explicit_starters","official_predictions")}))
if __name__=="__main__":main()
