"""#266: audit official NHL historical boxscore goalie starter field coverage.

Bounded, deterministic sample; no guessing starter from minutes, goalie ordering,
or one goalie's presence. Keep source digest and explicit failure status.
"""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from nhl.pulso_historical_boxscores_265 import fetch

def audit(labels,fetcher=fetch,limit=12):
    if not 1<=limit<=50:raise ValueError("Use a bounded 1..50 fixture sample")
    result=[];seen=set()
    for label in labels[:limit]:
        gid=str(label["game_id"])
        if gid in seen:raise ValueError("Duplicate historical game ID")
        seen.add(gid)
        row={"game_id":gid,"date":label["date"],"home":label["home"],"away":label["away"]}
        try:
            data,source=fetcher(gid)
            if str(data.get("id"))!=gid or data.get("gameDate")!=label["date"]:
                raise ValueError("Fixture identity mismatch")
            by_game=data.get("playerByGameStats")
            if not isinstance(by_game,dict):raise ValueError("Missing player stats")
            schema={}
            for side in ("home","away"):
                team=by_game.get(side+"Team")
                if not isinstance(team,dict) or not isinstance(team.get("goalies"),list):
                    raise ValueError("Missing goalie list")
                goalies=team["goalies"]
                ids=[g.get("playerId") for g in goalies]
                if len(set(ids))!=len(ids) or any(type(pid) is not int or pid<=0 for pid in ids):
                    raise ValueError("Invalid goalie IDs")
                explicit=[g["playerId"] for g in goalies if g.get("starter") is True]
                schema[side]={"goalie_count":len(goalies),"ids":ids,
                              "starter_field_count":sum(type(g.get("starter")) is bool for g in goalies),
                              "explicit_true_count":len(explicit),
                              "verified_starter_id":explicit[0] if len(explicit)==1 else None,
                              "available_field_names":sorted(set().union(*(set(g) for g in goalies))) if goalies else []}
            row.update(status="observed",source=source,teams=schema,
                       both_starters_explicit=all(schema[s]["verified_starter_id"] is not None for s in ("home","away")))
        except (OSError,ValueError,TypeError,KeyError) as error:
            row.update(status="blocked_"+type(error).__name__,both_starters_explicit=False)
        result.append(row)
    counts=Counter(x["status"] for x in result)
    return {"kind":"nhl_boxscore_schema_audit_266","sample_size":len(result),
            "both_starters_explicit":sum(x["both_starters_explicit"] for x in result),
            "status_counts":dict(counts),"games":result,
            "official_predictions":0,"calibrated":False,"odds_used":False,
            "note":"Sample coverage only; not representative population calibration."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=12)
    a=p.parse_args()
    with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
    result=audit(labels,limit=a.limit)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ("sample_size","both_starters_explicit","status_counts")}))
if __name__=="__main__":main()
