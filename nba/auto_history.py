"""Reconstruct verified NBA historical ledger for pregame prediction.

Completed 2023–26 seasons are audited and cleaned. For 2026–27, only prior
UTC days are included, so results later on prediction day cannot leak.
"""
import argparse,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from espn_games import ingest
from clean_regular import clean

COMPLETE_SEASONS=[(2024,"2023-10-24","2024-04-14"),
                  (2025,"2024-10-22","2025-04-13"),
                  (2026,"2025-10-21","2026-04-12")]
CURRENT_START=date(2026,10,20)

def build(output,game_date,as_of,root):
    day=date.fromisoformat(game_date)
    observed=datetime.fromisoformat(as_of.replace("Z","+00:00"))
    if observed.tzinfo is None or observed.utcoffset()!=timedelta(0):
        raise ValueError("UTC as_of required")
    # Do not fetch outcomes on or after the prediction day, or beyond now.
    current_end=min(day-timedelta(days=1),observed.date()-timedelta(days=1))
    base=Path(root);base.mkdir(parents=True,exist_ok=True)
    group=[]
    for season,start,end in COMPLETE_SEASONS:
        rows=ingest(base/str(season)/"raw.json",start,end)
        if any(int(g["season"])!=season for g in rows):
            raise ValueError(f"Unexpected historical season labels: {season}")
        group+=rows
    clean_history,audit=clean(group)
    if not audit["coverage_verified"] or len(clean_history)!=3690:
        raise ValueError("Historical training coverage not verified")
    current=[]
    if current_end>=CURRENT_START:
        current=ingest(base/"2027"/"prior_completed.json",
                       CURRENT_START.isoformat(),current_end.isoformat())
        if any(int(g["season"])!=2027 for g in current):
            raise ValueError("Current-season source classification wrong")
    ids=set()
    all_rows=sorted(clean_history+current,key=lambda g:(g["tipoff_utc"],str(g["game_id"])))
    for g in all_rows:
        if g["game_id"] in ids:raise ValueError("Duplicate historical ID")
        ids.add(g["game_id"])
        if datetime.fromisoformat(g["tipoff_utc"].replace("Z","+00:00"))>=observed:
            raise ValueError("History crosses snapshot time")
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(all_rows,indent=2))
    metadata={"created_at_utc":observed.isoformat(),"target_date":game_date,
       "clean_historical_games":len(clean_history),"current_prior_games":len(current),
       "source_count":len(all_rows),"cleaning":audit,
       "restriction":"No games on or after target UTC date"}
    (target.parent/"history_audit.json").write_text(json.dumps(metadata,indent=2))
    return metadata

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True);p.add_argument("--timestamp",required=True)
    p.add_argument("--output",required=True);p.add_argument("--workdir",required=True)
    args=p.parse_args()
    print(json.dumps(build(args.output,args.date,args.timestamp,args.workdir),indent=2))
