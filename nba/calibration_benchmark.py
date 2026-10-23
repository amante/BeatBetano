"""Compare chronological NBA Elo predictions with a fixed 50/50 baseline.

Calibration is descriptive on held-out games; no parameter is fitted on holdout.
"""
import math
from collections import defaultdict

def metrics(pairs):
    if not pairs:raise ValueError("No scored games")
    n=len(pairs)
    return {"n":n,"brier":sum((p-y)**2 for p,y in pairs)/n,
        "log_loss":-sum(y*math.log(max(1e-12,min(1-1e-12,p)))+
                    (1-y)*math.log1p(-max(1e-12,min(1-1e-12,p))) for p,y in pairs)/n,
        "accuracy":sum((p>=0.5)==bool(y) for p,y in pairs)/n}

def compare_holdout(predictions,games):
    warmup=[g for p,g in zip(predictions,games) if p.season==2024]
    if not warmup or any(g["home_points"] is None or g["away_points"] is None for g in warmup):
        raise ValueError("Complete 2023-24 warmup needed for home advantage benchmark")
    home_rate=sum(float(g["home_points"])>float(g["away_points"]) for g in warmup)/len(warmup)
    if not 0<home_rate<1:raise ValueError("Degenerate home advantage warmup")
    pairs=[]
    for p,g in zip(predictions,games):
        if p.game_id!=str(g["game_id"]):raise ValueError("Misaligned predictions")
        if p.season not in (2025,2026):continue
        if g["home_points"] is None or g["away_points"] is None:raise ValueError("Missing holdout result")
        y=int(float(g["home_points"])>float(g["away_points"]))
        pairs.append((p.season,p.p_home,y))
    if not pairs:raise ValueError("No holdout games")
    answer={}
    for year in (2025,2026):
        subset=[(p,y) for s,p,y in pairs if s==year]
        if not subset:raise ValueError(f"No games in holdout {year}")
        answer[str(year)]=_report(subset,home_rate)
    answer["pooled"]=_report([(p,y) for _,p,y in pairs],home_rate)
    answer["home_advantage_fit"]={"season_end_year":2024,"n":len(warmup),"home_win_rate":home_rate,"fit_on_holdout":False}
    return answer

def _report(rows,home_rate):
    elo=metrics(rows)
    coin=metrics([(0.5,y) for _,y in rows])
    home=metrics([(home_rate,y) for _,y in rows])
    bins=[]
    for lower in range(0,100,10):
        subset=[(p,y) for p,y in rows if (lower/100<=p<(lower+10)/100 or (lower==90 and p==1))]
        bins.append({"range":[lower/100,(lower+10)/100],"n":len(subset),
                     "mean_forecast":sum(p for p,y in subset)/len(subset) if subset else None,
                     "observed_home_win_rate":sum(y for p,y in subset)/len(subset) if subset else None})
    return {"elo":elo,"fifty_fifty_baseline":coin,"home_only_baseline":home,
            "brier_improvement_vs_home_only":home["brier"]-elo["brier"],
            "log_loss_improvement_vs_home_only":home["log_loss"]-elo["log_loss"],
            "brier_improvement_vs_fifty_fifty":coin["brier"]-elo["brier"],
            "log_loss_improvement_vs_fifty_fifty":coin["log_loss"]-elo["log_loss"],
            "reliability_bins":bins,
            "calibrated":False}
