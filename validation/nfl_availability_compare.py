"""Availability Delta 2.3: paired, chronological and deliberately limited comparison.

Train on 2023, test on 2024. Both models fit on identical complete-case games.
Not a claim about starter roles or causal effects of injuries.
"""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from nfl_epa import build,FEATURES
from nfl_availability import availability_features,attach_availability

def run(games_path,pbp_path,injury_path,out):
    games=pd.read_csv(games_path,low_memory=False)
    pbp=pd.read_parquet(pbp_path)
    snapshots=pd.read_csv(injury_path,low_memory=False)
    features=build(games,pbp)
    paired=attach_availability(games,availability_features(snapshots))
    count_cols=[c for c in paired.columns if c.startswith("home_out_") or c.startswith("away_out_")]
    merged=features.merge(paired[["season","game_id","home_team","away_team"]+count_cols].rename(columns={"home_team":"home","away_team":"away"}),
        on=["season","home","away"],how="inner",validate="one_to_one")
    # NFL teams meet once/twice per year, so joining on season/team pair can be ambiguous.
    # Fail closed rather than silently misattributing reports.
    train=merged[merged.season==2023].copy()
    test=merged[merged.season==2024].copy()
    if len(train)<150 or len(test)<150:raise ValueError(f"Insufficient complete-case games: {len(train)} train, {len(test)} test")
    availability=[f"home_out_{p}" for p in ["qb","ol","edge","dt","lb","cb","s"]]+[f"away_out_{p}" for p in ["qb","ol","edge","dt","lb","cb","s"]]
    y=test.home_win.to_numpy(dtype=float)
    result={"train_games":len(train),"test_games":len(test),"train_year":2023,"test_year":2024,
            "caveat":"Only injury-report counts, not confirmed inactives or CB1/CB2/nickel; small training window."}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    predictions=test[["season","date","home","away","home_win"]].copy()
    for label,cols in [("epa",FEATURES),("epa_plus_injury_counts",FEATURES+availability)]:
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.05,max_iter=2000,random_state=0))
        model.fit(train[cols],train.home_win)
        prob=np.clip(model.predict_proba(test[cols])[:,1],1e-8,1-1e-8)
        predictions["p_"+label]=prob
        result[label]={"brier":float(np.mean((prob-y)**2)),
                       "log_loss":float(np.mean(-y*np.log(prob)-(1-y)*np.log1p(-prob)))}
    result["delta_brier"]=result["epa_plus_injury_counts"]["brier"]-result["epa"]["brier"]
    result["delta_log_loss"]=result["epa_plus_injury_counts"]["log_loss"]-result["epa"]["log_loss"]
    predictions.to_csv(out/"paired_predictions.csv",index=False)
    (out/"comparison.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ["games","pbp","injuries","output"]:p.add_argument("--"+field,required=True)
    a=p.parse_args();run(a.games,a.pbp,a.injuries,a.output)
