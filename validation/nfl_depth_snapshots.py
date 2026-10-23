"""Historical NFL depth-chart point-in-time *candidate* snapshots.

2025+ nflverse/ESPN data has 'dt' capture timestamps. Select the last captured
team snapshot strictly before the kickoff. Depth rank is NOT confirmed starter
status, an injury/active designation, or CB1 coverage assignment.
"""
import argparse, json
from io import BytesIO
from pathlib import Path
import pandas as pd
import requests

URL="https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_{season}.csv"
REQUIRED={"dt","team","gsis_id","pos_abb","pos_slot","pos_rank"}
def fetch(season):
    if season<2025:raise ValueError("Dated nflverse depth charts begin in 2025")
    r=requests.get(URL.format(season=season),timeout=150)
    r.raise_for_status()
    return pd.read_csv(BytesIO(r.content),low_memory=False)

def select_pregame_depth(games,depth):
    needed_games={"game_id","season","gameday","gametime","home_team","away_team"}
    if not needed_games.issubset(games.columns):raise ValueError("Schedule missing required fields")
    if not REQUIRED.issubset(depth.columns):raise ValueError(f"Missing depth fields: {sorted(REQUIRED-set(depth.columns))}")
    g=games.copy()
    local=pd.to_datetime(g.gameday.astype(str)+" "+g.gametime.astype(str),errors="coerce")
    g["kickoff_utc"]=local.dt.tz_localize("America/New_York",ambiguous="NaT",nonexistent="NaT").dt.tz_convert("UTC")
    g=g.dropna(subset=["kickoff_utc"])
    if g.game_id.duplicated().any():raise ValueError("Duplicate game identity")
    d=depth.copy()
    d["dt"]=pd.to_datetime(d.dt,utc=True,errors="coerce")
    d=d.dropna(subset=["dt","team","gsis_id","pos_abb","pos_slot","pos_rank"])
    d["pos_rank"]=pd.to_numeric(d.pos_rank,errors="coerce")
    d=d.dropna(subset=["pos_rank"])
    teams=pd.concat([
       g[["game_id","season","kickoff_utc","home_team"]].rename(columns={"home_team":"team"}),
       g[["game_id","season","kickoff_utc","away_team"]].rename(columns={"away_team":"team"})
    ],ignore_index=True)
    result=[]
    for (season,team),block in teams.groupby(["season","team"]):
        dd=d[d.team.eq(team)].copy()
        dd=dd.sort_values("dt")
        for game in block.itertuples(index=False):
            eligible=dd[dd.dt < game.kickoff_utc]
            if eligible.empty:continue
            timestamp=eligible.dt.max()
            snap=eligible[eligible.dt.eq(timestamp)].copy()
            snap["game_id"]=game.game_id
            snap["kickoff_utc"]=game.kickoff_utc
            result.append(snap)
    if not result:
        return pd.DataFrame(columns=["game_id","team","gsis_id","pos_abb","pos_slot","pos_rank","dt","kickoff_utc"])
    out=pd.concat(result,ignore_index=True)
    if not (out.dt<out.kickoff_utc).all():raise ValueError("Post-kickoff data leak")
    return out

def run(games_path,output,seasons):
    games=pd.read_csv(games_path,low_memory=False)
    selected=[]
    coverage=[]
    for year in seasons:
        g=games[games.season.eq(year)].copy()
        charts=fetch(year)
        snap=select_pregame_depth(g,charts)
        snap["season"]=year
        selected.append(snap)
        total=len(g)*2
        pairs=snap[["game_id","team"]].drop_duplicates()
        count=len(pairs)
        coverage.append({"season":year,"games":len(g),"team_game_snapshots":count,
                         "team_game_coverage_pct":round(count/total*100,2) if total else 0})
    o=Path(output);o.mkdir(parents=True,exist_ok=True)
    pd.concat(selected,ignore_index=True).to_csv(o/"pregame_depth_candidates.csv",index=False)
    (o/"coverage.json").write_text(json.dumps(coverage,indent=2))
    print(json.dumps(coverage,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--seasons",type=int,nargs="+",default=[2025])
    a=p.parse_args()
    run(a.games,a.output,a.seasons)
