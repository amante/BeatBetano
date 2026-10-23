"""NFL Next Gen Stats weekly historical ingestion and lagged player signals.

Source: nflverse release nextgen_stats/ngs_{passing,receiving,rushing}.parquet
Explicitly exclude week=0 season aggregates and never use a target week's data.
"""
import argparse, json
from io import BytesIO
from pathlib import Path
import pandas as pd
import requests

URL="https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_{kind}.parquet"
KINDS=("passing","receiving","rushing")
BASE={"season","week","player_gsis_id","team_abbr"}
METRICS={
 "passing":("avg_time_to_throw","avg_intended_air_yards","completion_percentage_above_expectation"),
 "receiving":("avg_separation","avg_cushion","avg_yac_above_expectation"),
 "rushing":("rush_yards_over_expected_per_att","efficiency","percent_attempts_gte_eight_defenders")
}

def clean(df,kind,last_season=2025):
    if kind not in KINDS:raise ValueError("Unknown NGS kind")
    if not BASE.issubset(df.columns):raise ValueError(f"Missing {sorted(BASE-set(df.columns))}")
    d=df.copy()
    d["season"]=pd.to_numeric(d.season,errors="coerce")
    d["week"]=pd.to_numeric(d.week,errors="coerce")
    d=d[(d.season>=2016)&(d.season<=last_season)&(d.week>=1)&(d.week<=22)]
    d=d.dropna(subset=["season","week","player_gsis_id","team_abbr"])
    d["season"]=d.season.astype(int);d["week"]=d.week.astype(int)
    # No season aggregate week 0, which would leak future data.
    if d.duplicated(["season","week","player_gsis_id"]).any():
        raise ValueError(f"Duplicate player/week rows: {kind}")
    d["kind"]=kind
    return d

def previous_week_features(d,kind):
    """Only past-week records for same player within same season.

    Weeks without an NGS record remain unknown; no filling with future data.
    """
    if kind not in KINDS:raise ValueError("Invalid kind")
    metrics=[c for c in METRICS[kind] if c in d.columns]
    if not metrics:raise ValueError(f"No known {kind} NGS metrics")
    d=d.sort_values(["player_gsis_id","season","week"]).copy()
    # For each weekly observation calculate means from strictly earlier weeks.
    for c in metrics:
        d[f"prior_{c}"]=d.groupby(["season","player_gsis_id"])[c].transform(
            lambda s:s.shift(1).expanding(min_periods=1).mean()
        )
    d["prior_weeks_observed"]=d.groupby(["season","player_gsis_id"]).cumcount()
    return d[["season","week","player_gsis_id","team_abbr","kind","prior_weeks_observed"]+
             [f"prior_{c}" for c in metrics]]

def fetch(kind,timeout=120):
    url=URL.format(kind=kind)
    r=requests.get(url,timeout=timeout);r.raise_for_status()
    return pd.read_parquet(BytesIO(r.content))

def run(out,last_season=2025):
    o=Path(out);o.mkdir(parents=True,exist_ok=True)
    report=[]
    for kind in KINDS:
        d=clean(fetch(kind),kind,last_season)
        d.to_parquet(o/f"ngs_{kind}_weekly.parquet",index=False)
        prior=previous_week_features(d,kind)
        prior.to_parquet(o/f"ngs_{kind}_prior.parquet",index=False)
        report.append({"kind":kind,"rows":len(d),"seasons":int(d.season.nunique()),
                       "first_season":int(d.season.min()),"last_season":int(d.season.max()),
                       "prior_rows":int((prior.prior_weeks_observed>0).sum())})
    (o/"coverage.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--last-season",type=int,default=2025)
    a=p.parse_args()
    run(a.output,a.last_season)
