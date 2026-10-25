"""Settle a frozen NBA prospective snapshot against verified ESPN final scores.

Never changes the original snapshot. Partial results are explicitly reported.
"""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from current_feed import fetch_day
from prospective import settle

def verify_snapshot(snapshot):
    digest=snapshot.get("content_sha256")
    if not isinstance(digest,str):raise ValueError("Missing snapshot digest")
    body={k:v for k,v in snapshot.items() if k!="content_sha256"}
    actual=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if actual!=digest:raise ValueError("Snapshot digest mismatch")
    if not snapshot.get("predictions"):raise ValueError("Empty prediction snapshot")
    return True

def report(snapshot,results):
    verify_snapshot(snapshot)
    settled=settle(snapshot,results)
    settled["unsettled_games"]=settled["total_predictions"]-settled["settled_games"]
    settled["complete"]=settled["unsettled_games"]==0
    settled["models_are_calibrated"]=False
    settled["interpretation"]="Prospective diagnostic only; no betting approval"
    return settled

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--as-of",required=True)
    args=ap.parse_args()
    snap=json.loads(Path(args.snapshot).read_text())
    verify_snapshot(snap)
    now=datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
    if now.tzinfo is None or now.utcoffset()!=timedelta(0):raise ValueError("UTC as-of required")
    # ESPN scoreboard day is a US calendar date. Query all days of the
    # predictions (UTC days) and their immediate neighboring dates to cover
    # games starting around midnight and league-date boundaries.
    days=set()
    for pred in snap["predictions"]:
        dt=datetime.fromisoformat(pred["tipoff_utc"].replace("Z","+00:00")).date()
        for shift in (-1,0,1):
            days.add((dt+timedelta(days=shift)).isoformat())
    by_id={}
    for day in sorted(days):
        payload=fetch_day(day,now.isoformat())
        for g in payload["completed_games"]:
            key=str(g["game_id"])
            if key in by_id and by_id[key]!=g:raise ValueError("Conflicting final scores")
            by_id[key]=g
    result=report(snap,list(by_id.values()))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
