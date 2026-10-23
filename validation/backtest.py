#!/usr/bin/env python3
"""Historical sports-model evaluation MVP; never uses betting odds."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

NFL_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

def brier(p, y):
    return float(np.mean((np.asarray(p, dtype=float)-np.asarray(y, dtype=float))**2))

def logloss(p, y):
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1-1e-8)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))

def reliability(p, y, bins=10):
    d = pd.DataFrame({"p":p,"y":y})
    d["bucket"] = np.minimum((d.p*bins).astype(int), bins-1)
    return d.groupby("bucket").agg(n=("y","size"),predicted=("p","mean"),observed=("y","mean")).reset_index()

def nfl(input_path, output):
    df = pd.read_csv(input_path, low_memory=False)
    required = {"home_team","away_team","home_score","away_score","season","gameday"}
    missing = required-set(df.columns)
    if missing: raise ValueError(f"Missing NFL columns: {sorted(missing)}")
    df = df.dropna(subset=list(required)).copy()
    if "game_type" in df: df = df[df.game_type.isin(["REG","WC","DIV","CON","SB"])]
    df["date"] = pd.to_datetime(df.gameday, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values(["season","date","week"] if "week" in df else ["season","date"])
    ties = int((df.home_score == df.away_score).sum())
    df = df[df.home_score != df.away_score]
    ratings, rows, prev_season = {}, [], None
    for (season, day), batch in df.groupby(["season","date"], sort=True):
        if prev_season is not None and season != prev_season:
            ratings = {team:1500+0.75*(rating-1500) for team,rating in ratings.items()}
        prev_season = season
        batch_predictions = []
        for r in batch.itertuples():
            home, away = ratings.get(r.home_team,1500), ratings.get(r.away_team,1500)
            p = 1/(1+10**(-(home-away+55)/400))
            actual = int(r.home_score > r.away_score)
            rows.append({"season":int(season),"date":str(day.date()),"home":r.home_team,"away":r.away_team,"p_home":p,"home_win":actual})
            batch_predictions.append((r.home_team,r.away_team,p,actual))
        # All predictions for this date are frozen before rating changes.
        for home_team,away_team,p,actual in batch_predictions:
            delta = 20*(actual-p)
            ratings[home_team] = ratings.get(home_team,1500)+delta
            ratings[away_team] = ratings.get(away_team,1500)-delta
    if not rows: raise ValueError("No eligible NFL games")
    pred = pd.DataFrame(rows)
    seasons = sorted(pred.season.unique())
    test_seasons = seasons[-2:] if len(seasons)>=5 else seasons[-1:]
    test = pred[pred.season.isin(test_seasons)]
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    pred.to_csv(output/"pregame_predictions.csv",index=False)
    reliability(test.p_home,test.home_win).to_csv(output/"reliability.csv",index=False)
    metrics = {"model":"elo_baseline_not_official","games":len(pred),"ties_excluded":ties,
               "test_seasons":[int(x) for x in test_seasons],"test_games":len(test),
               "brier":brier(test.p_home,test.home_win),
               "log_loss":logloss(test.p_home,test.home_win)}
    (output/"metrics.json").write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics,indent=2))

def nba20(input_path, output):
    d = pd.read_csv(input_path,low_memory=False)
    def col(options):
        for name in options:
            if name in d.columns: return name
        raise ValueError(f"NBA play-by-play needs one of {options}")
    gid=col(["game_id","gameId","gameid"])
    home=col(["home_score","homeScore","home_score_value"])
    away=col(["away_score","awayScore","away_score_value"])
    x=d[[gid,home,away]].copy()
    x[home]=pd.to_numeric(x[home],errors="coerce")
    x[away]=pd.to_numeric(x[away],errors="coerce")
    x=x.dropna(subset=[gid,home,away])
    if x.empty: raise ValueError("No valid score-bearing NBA events")
    x["margin"]=x[home]-x[away]
    results=x.groupby(gid).agg(max_home_lead=("margin","max"),max_away_lead=("margin",lambda v:-v.min()),events=("margin","size"))
    results["any_20_plus"] = ((results.max_home_lead>=20)|(results.max_away_lead>=20)).astype(int)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results.to_csv(output/"nba_20_events.csv")
    summary={"games":len(results),"games_with_20_plus":int(results.any_20_plus.sum()),
             "empirical_frequency":float(results.any_20_plus.mean()),
             "warning":"Observed event extraction, NOT a calibrated pregame probability."}
    (output/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    for cmd in ("nfl","nba-20"):
        q=sub.add_parser(cmd);q.add_argument("--input",required=True);q.add_argument("--output",required=True)
    q=sub.add_parser("fetch-nfl");q.add_argument("--output",default="nfl_games.csv")
    args=p.parse_args()
    if args.cmd=="nfl": nfl(args.input,args.output)
    elif args.cmd=="nba-20": nba20(args.input,args.output)
    else:
        import requests
        response=requests.get(NFL_URL,timeout=60);response.raise_for_status()
        target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(response.content)
        print(f"Saved {len(response.content)} bytes to {target}")

if __name__=="__main__": main()
