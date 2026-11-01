"""NHL #269: research-only, time-split goalie-conditioned ML logistic benchmark.

Fits only 4 dated sporting covariates. Calibration fitted exclusively on
validation; final holdout is never touched for fitting or model selection.
"""
import argparse,json,math
from pathlib import Path

FEATURES=("home_goalie_prior_sv","away_goalie_prior_sv","home_team_prior_strength","away_team_prior_strength")
def sigmoid(x):
    if x>=0:return 1/(1+math.exp(-min(x,700)))
    e=math.exp(max(x,-700));return e/(1+e)
def logit(x):return math.log(max(1e-7,min(1-1e-7,x))/(1-max(1e-7,min(1-1e-7,x))))
def vector(r):
    values=[float(r[k]) for k in FEATURES]
    if not all(math.isfinite(x) for x in values):raise ValueError("Nonfinite feature")
    if not all(0<=x<=1 for x in values[:2]):raise ValueError("Invalid save percentage")
    return values
def split(rows):
    dates=sorted(set(r["date"] for r in rows))
    if len(dates)<6:raise ValueError("Insufficient distinct dates")
    end_fit=dates[int(len(dates)*.6)-1];end_val=dates[int(len(dates)*.8)-1]
    groups=([r for r in rows if r["date"]<=end_fit],
            [r for r in rows if end_fit<r["date"]<=end_val],
            [r for r in rows if r["date"]>end_val])
    if any(not group for group in groups):raise ValueError("Empty chronological partition")
    return groups,(end_fit,end_val)
def train(xs,ys,l2=.02,steps=1500,rate=.05):
    n=len(xs);dim=len(xs[0]);mean=[sum(x[j] for x in xs)/n for j in range(dim)]
    scale=[max(.01,(sum((x[j]-mean[j])**2 for x in xs)/n)**.5) for j in range(dim)]
    normalized=[[1.]+[(x[j]-mean[j])/scale[j] for j in range(dim)] for x in xs]
    coef=[0.]*(dim+1);coef[0]=logit((sum(ys)+.5)/(n+1))
    for _ in range(steps):
        grad=[0.]*(dim+1)
        for x,y in zip(normalized,ys):
            error=sigmoid(sum(a*b for a,b in zip(coef,x)))-y
            for j in range(dim+1):grad[j]+=error*x[j]
        for j in range(dim+1):
            grad[j]=grad[j]/n+(l2*coef[j] if j else 0.)
            coef[j]-=rate*grad[j]
    return {"coef":coef,"mean":mean,"scale":scale}
def predict(model,x):
    features=[1.]+[(v-m)/s for v,m,s in zip(x,model["mean"],model["scale"])]
    return sigmoid(sum(a*b for a,b in zip(model["coef"],features)))
def score(probs,ys):
    if not probs:raise ValueError("Empty evaluation")
    return {"n":len(ys),"brier":round(sum((p-y)**2 for p,y in zip(probs,ys))/len(ys),6),
            "log_loss":round(-sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y in zip(probs,ys))/len(ys),6)}
def evaluate(report):
    if report.get("kind")!="nhl_historical_goalie_features_267" or report.get("odds_used") is not False or report.get("calibrated") is not False:
        raise ValueError("Untrusted historical evidence")
    if report.get("source_game_count")!=2811 or report.get("batch_report",{}).get("complete_source_coverage") is not True:
        raise ValueError("Incomplete historical source collection")
    rows=report["eligible_rows"]
    if len(rows)!=report["eligible_count"] or len({r["game_id"] for r in rows})!=len(rows):
        raise ValueError("Invalid historical row identity")
    groups,(fit_until,val_until)=split(rows)
    if min(map(len,groups))<100:raise ValueError("Insufficient independent sample")
    for r in rows:
        if not r["feature_as_of_date"]<r["date"] or r["ml_winner"] not in ("home","away"):raise ValueError("Temporal leakage or bad label")
        vector(r)
    fit,val,test=groups
    features=lambda group:[vector(r) for r in group]
    outcomes=lambda group:[int(r["ml_winner"]=="home") for r in group]
    xfit=features(fit);yfit=outcomes(fit)
    model=train(xfit,yfit)
    # Platt calibration: fit two parameters to validation logits only.
    val_raw=[predict(model,x) for x in features(val)]
    calibration=train([[logit(p)] for p in val_raw],outcomes(val),l2=.005)
    test_raw=[predict(model,x) for x in features(test)]
    test_cal=[predict(calibration,[logit(p)]) for p in test_raw]
    baseline=(sum(yfit)+.5)/(len(yfit)+1)
    baseline_probs=[baseline]*len(test)
    result={"kind":"nhl_goalie_ml_research_backtest_269","source_games":2811,
            "eligible_rows":len(rows),"fit_n":len(fit),"validation_n":len(val),"holdout_n":len(test),
            "fit_until":fit_until,"validation_until":val_until,
            "feature_names":list(FEATURES),
            "baseline_holdout":score(baseline_probs,outcomes(test)),
            "uncalibrated_holdout":score(test_raw,outcomes(test)),
            "calibrated_holdout":score(test_cal,outcomes(test)),
            "raw_model":model,"validation_platt_model":calibration,
            "odds_used":False,"official_predictions":0,"automatic_promotion":False,
            "independently_validated":False,
            "note":"Research-only ML benchmark: no independent point-in-time source snapshots, RT/+3/Rescue models, or approved deployment."}
    result["beats_baseline_brier"]=result["calibrated_holdout"]["brier"]<result["baseline_holdout"]["brier"]
    result["beats_baseline_log_loss"]=result["calibrated_holdout"]["log_loss"]<result["baseline_holdout"]["log_loss"]
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--features",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=evaluate(json.loads(Path(a.features).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ("fit_n","validation_n","holdout_n","baseline_holdout","calibrated_holdout","beats_baseline_brier","beats_baseline_log_loss")}))
if __name__=="__main__":main()
