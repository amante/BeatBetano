"""Chronological rolling-origin evaluation of incremental NFL availability features.

Requires *existing* pregame features and labels; never infers starter status from
postgame participation. Every evaluation year fits both models only on past years.
"""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from nfl_epa import FEATURES
from paired_uncertainty import evaluate

def walkforward(frame,min_train=500,min_test=100):
    required={"season","game_id","home_win"}|set(FEATURES)
    missing=required-set(frame.columns)
    if missing:raise ValueError(f"Missing {sorted(missing)}")
    extra=sorted(c for c in frame.columns if c.startswith(("home_out_","away_out_")))
    if len(extra)!=14:raise ValueError("Require seven injury counts for both teams; missing fields must not mean healthy")
    if frame.game_id.duplicated().any():raise ValueError("Duplicate game IDs")
    if frame[list(required)+extra].isna().any().any():raise ValueError("Incomplete pregame feature data")
    f=frame.copy();preds=[]
    for year in sorted(f.season.unique()):
        train=f[f.season<year]
        test=f[f.season==year]
        if len(train)<min_train or len(test)<min_test:continue
        out=test[["season","game_id","home_win"]].copy()
        for label,cols in (("epa",FEATURES),("epa_plus_injury_counts",FEATURES+extra)):
            model=make_pipeline(StandardScaler(),LogisticRegression(C=.05,max_iter=2000,random_state=0))
            model.fit(train[cols],train.home_win)
            out["p_"+label]=model.predict_proba(test[cols])[:,1]
        preds.append(out)
    if not preds:raise ValueError("No qualifying chronological holdout; need multiple earlier seasons")
    combined=pd.concat(preds,ignore_index=True)
    report=evaluate(combined)
    report["holdout_seasons"]=sorted(int(x) for x in combined.season.unique())
    report["conclusion"]="exploratory_only" if len(report["holdout_seasons"])<3 else "evaluate_promotion_gates"
    return combined,report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--features",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    preds,report=walkforward(pd.read_csv(a.features))
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    preds.to_csv(out/"walkforward_predictions.csv",index=False)
    (out/"walkforward_summary.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
