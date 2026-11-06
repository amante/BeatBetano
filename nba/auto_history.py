"""Reconstruct verified NBA historical ledger for pregame prediction.

Completed 2023–26 seasons are audited and cleaned. For 2026–27, only prior
UTC days are included, so results later on prediction day cannot leak.
"""
import argparse,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from history_store import frozen_history, daily_delta
from prepared_history_gate import prior_utc_history

CURRENT_START=date(2026,10,20)

def build(output,game_date,as_of,root):
    day=date.fromisoformat(game_date)
    observed=datetime.fromisoformat(as_of.replace("Z","+00:00"))
    if observed.tzinfo is None or observed.utcoffset()!=timedelta(0):
        raise ValueError("UTC as_of required")
    # Do not fetch outcomes on or after the prediction day, or beyond now.
    current_end=min(day-timedelta(days=1),observed.date()-timedelta(days=1))
    base=Path(root);base.mkdir(parents=True,exist_ok=True)
    clean_history,audit=frozen_history()
    current=[]
    delta_audit={"requested_dates":[],"reused_dates":[],"network_requests":0}
    if current_end>=CURRENT_START:
        current,delta_audit=daily_delta(base/"2027"/"daily",
                       CURRENT_START.isoformat(),current_end.isoformat())
        if any(int(g["season"])!=2027 for g in current):
            raise ValueError("Current-season source classification wrong")
    current,excluded_utc_ids=prior_utc_history(current,game_date)
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
       "source_count":len(all_rows),"delta":delta_audit,"excluded_target_utc_game_ids":excluded_utc_ids,"cleaning":audit,
       "restriction":"No games on or after target UTC date"}
    (target.parent/"history_audit.json").write_text(json.dumps(metadata,indent=2))
    return metadata

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True);p.add_argument("--timestamp",required=True)
    p.add_argument("--output",required=True);p.add_argument("--workdir",required=True)
    args=p.parse_args()
    print(json.dumps(build(args.output,args.date,args.timestamp,args.workdir),indent=2))
