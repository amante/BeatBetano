"""Paired uncertainty for NFL model comparisons. Lower Brier/log loss is better.

Season-block bootstrap, rather than treating every NFL game as independent,
when multiple holdout seasons are present. One season => exploratory only.
"""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd

def evaluate(df,base="p_epa",chall="p_epa_plus_injury_counts",samples=4000,seed=42):
    required={"season","home_win",base,chall}
    if not required.issubset(df):raise ValueError(f"Missing {required-set(df)}")
    if df.empty or df[list(required)].isna().any().any():raise ValueError("Empty/incomplete paired evaluation")
    y=df.home_win.to_numpy(dtype=float)
    a=np.clip(df[base].to_numpy(dtype=float),1e-8,1-1e-8)
    b=np.clip(df[chall].to_numpy(dtype=float),1e-8,1-1e-8)
    if not np.isin(y,[0,1]).all():raise ValueError("Invalid outcomes")
    losses={
      "brier":(b-y)**2-(a-y)**2,
      "log_loss":-y*np.log(b)-(1-y)*np.log1p(-b)+y*np.log(a)+(1-y)*np.log1p(-a)
    }
    rng=np.random.default_rng(seed)
    seasons=np.unique(df.season.to_numpy())
    report={"n_games":len(df),"n_seasons":len(seasons),"bootstrap_unit":"season" if len(seasons)>=2 else "game_exploratory",
            "note":"One holdout season: game resampling understates dependence and is not a robust generalization test" if len(seasons)==1 else "Season-cluster uncertainty; few seasons imply fragile intervals"}
    for metric,d in losses.items():
        draws=[]
        for _ in range(samples):
            if len(seasons)>1:
                picked=rng.choice(seasons,size=len(seasons),replace=True)
                indices=np.concatenate([np.flatnonzero(df.season.to_numpy()==s) for s in picked])
            else:
                indices=rng.integers(0,len(d),size=len(d))
            draws.append(float(np.mean(d[indices])))
        report[metric]={"challenger_minus_baseline":float(np.mean(d)),
          "ci95":[float(q) for q in np.percentile(draws,[2.5,97.5])],
          "bootstrap_samples":samples}
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--predictions",required=True);p.add_argument("--output",required=True)
    p.add_argument("--base",default="p_epa");p.add_argument("--challenger",default="p_epa_plus_injury_counts")
    a=p.parse_args()
    result=evaluate(pd.read_csv(a.predictions),a.base,a.challenger)
    o=Path(a.output);o.parent.mkdir(parents=True,exist_ok=True)
    o.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
