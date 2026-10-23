"""Conservative nflverse 2023–24 injury ingest, requiring timestamps before kickoff.

Archived final records are *not* assumed to have been known before kickoff.
Unknown report coverage is not treated as a healthy roster.
"""
import argparse, json
from io import BytesIO
from pathlib import Path
import pandas as pd
import requests
from nfl_availability import availability_features, attach_availability

URL="https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
REQUIRED={"season","week","team","gsis_id","position","report_status","date_modified"}
# Explicitly conservative: uncertain statuses are not counted as out
OUT_STATUSES={"OUT","IR","INACTIVE","SUSPENDED"}
POSITION_MAP={"QB":"QB","CB":"CB","DB":"CB","S":"S","SS":"S","FS":"S","LB":"LB",
              "ILB":"LB","OLB":"LB","DE":"EDGE","EDGE":"EDGE","DT":"DT","NT":"DT",
              "T":"OL","G":"OL","C":"OL","OT":"OL","OG":"OL"}

def normalize(games,reports):
    missing=REQUIRED-set(reports.columns)
    if missing:raise ValueError(f"Missing injury source columns: {sorted(missing)}")
    needed={"game_id","season","week","home_team","away_team","gameday","gametime"}
    missing=needed-set(games.columns)
    if missing:raise ValueError(f"Missing schedule columns: {sorted(missing)}")
    g=games.copy();r=reports.copy()
    g["kickoff_utc"]=pd.to_datetime(g.gameday.astype(str)+" "+g.gametime.astype(str),
                                    utc=True,errors="coerce")
    # NFL gametime from nflverse is Eastern (ET), NOT UTC; localize in America/New_York.
    local=pd.to_datetime(g.gameday.astype(str)+" "+g.gametime.astype(str),errors="coerce")
    g["kickoff_utc"]=local.dt.tz_localize("America/New_York",ambiguous="NaT",nonexistent="NaT").dt.tz_convert("UTC")
    g=g.dropna(subset=["kickoff_utc"])
    if g.game_id.duplicated().any():raise ValueError("Duplicate games")
    teams=pd.concat([g[["game_id","season","week","kickoff_utc","home_team"]].rename(columns={"home_team":"team"}),
                     g[["game_id","season","week","kickoff_utc","away_team"]].rename(columns={"away_team":"team"})],
                     ignore_index=True)
    teams["team"]=teams.team.astype(str)
    r["date_modified"]=pd.to_datetime(r.date_modified,utc=True,errors="coerce")
    r=r.dropna(subset=["date_modified","gsis_id","team"])
    r=r.merge(teams,on=["season","week","team"],how="inner",validate="many_to_one")
    # Reject final reports generated/modified after kickoff: not knowable pregame.
    r=r[r.date_modified<=r.kickoff_utc].copy()
    r["position"]=r.position.astype(str).str.upper().map(POSITION_MAP)
    r=r.dropna(subset=["position"])
    r["status"]=r.report_status.fillna("UNSPECIFIED").astype(str).str.upper().str.strip()
    r["player_id"]=r.gsis_id.astype(str)
    r["snapshot_utc"]=r.date_modified
    r["source"]="nflverse_injuries_asof"
    columns=["game_id","team","player_id","position","status","snapshot_utc","kickoff_utc","source"]
    return r[columns].copy()

def run(schedule_path,outdir,start=2023,end=2024):
    if end>2024:raise ValueError("nflverse injury data not available after 2024")
    g=pd.read_csv(schedule_path,low_memory=False)
    g=g[g.season.between(start,end)].copy()
    reports=[]
    for season in range(start,end+1):
        resp=requests.get(URL.format(season=season),timeout=150);resp.raise_for_status()
        df=pd.read_csv(BytesIO(resp.content),low_memory=False)
        reports.append(df)
        print(f"season {season}: {len(df)} archive rows")
    normalized=normalize(g,pd.concat(reports,ignore_index=True))
    o=Path(outdir);o.mkdir(parents=True,exist_ok=True)
    normalized.to_csv(o/"pregame_snapshots.csv",index=False)
    matched=attach_availability(g,availability_features(normalized))
    totals=g.groupby("season").size()
    covered=matched.groupby("season").size()
    report=[]
    for year,total in totals.items():
        n=int(covered.get(year,0))
        report.append({"season":int(year),"games":int(total),"paired_games":n,"coverage_pct":round(100*n/total,2)})
    (o/"coverage.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({"eligible_pregame_rows":len(normalized),"coverage":report},indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--output",required=True)
    p.add_argument("--start",type=int,default=2023);p.add_argument("--end",type=int,default=2024)
    a=p.parse_args();run(a.games,a.output,a.start,a.end)
