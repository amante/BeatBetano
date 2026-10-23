"""Point-in-time NBA advanced player metrics: validation and prior-year features.

Source rows are provided separately from an authorized exporter. This module
never scrapes blocked websites and never treats full-season aggregates as if
they existed during that season.
"""
from collections import defaultdict
import math

METRICS=("per","ts_pct","bpm","vorp","ws_per_48")

def validate_rows(rows):
    seen=set()
    for r in rows:
        required={"player_id","season_end_year","team","games","minutes"}|set(METRICS)
        missing=required-set(r)
        if missing:raise ValueError(f"Missing advanced fields: {sorted(missing)}")
        key=(str(r["player_id"]),int(r["season_end_year"]),str(r["team"]))
        if key in seen:raise ValueError(f"Duplicate player-season-team {key}")
        seen.add(key)
        if not key[0] or not key[2] or int(r["games"])<0 or float(r["minutes"])<0:
            raise ValueError("Invalid player-season values")
        for m in METRICS:
            v=r[m]
            if v is not None and not math.isfinite(float(v)):
                raise ValueError(f"Nonfinite {m}")
    return True

def last_completed_season_features(rows,target_season_end_year):
    """For games in NBA season ending YEAR, only include YEAR-1 and earlier.

    Multi-team player seasonal rows are ambiguous: reject rather than
    double-count; prepare a single verified TOT row upstream if appropriate.
    """
    validate_rows(rows)
    cutoff=int(target_season_end_year)-1
    eligible=[r for r in rows if int(r["season_end_year"])<=cutoff]
    by_player=defaultdict(list)
    for r in eligible:by_player[str(r["player_id"])].append(r)
    output=[]
    for pid,values in by_player.items():
        latest=max(int(r["season_end_year"]) for r in values)
        recent=[r for r in values if int(r["season_end_year"])==latest]
        if len(recent)!=1:
            continue
        r=recent[0]
        out={"player_id":pid,"feature_season_end_year":latest,
             "latest_team":str(r["team"]),"prior_minutes":float(r["minutes"])}
        for metric in METRICS:
            out[f"prior_{metric}"]=None if r[metric] is None else float(r[metric])
        output.append(out)
    return sorted(output,key=lambda r:r["player_id"])
