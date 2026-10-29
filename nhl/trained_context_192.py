"""NHL #192: genuinely fitted, chronological ML research coefficients.

Uses prior-date team-outcome baseline and schedule-only covariates. Fits a
regularized logistic offset model on strictly earlier games; reports walk-forward
out-of-sample ML probabilities. Not the official 14-module NHL model.
"""
import argparse,csv,json,math
from datetime import date
from pathlib import Path
try:
 from nhl.historical_target_walkforward import read_labels,timeline
 from nhl.integrated_ablation_audit_186 import context
except ModuleNotFoundError:
 from historical_target_walkforward import read_labels,timeline
 from integrated_ablation_audit_186 import context

def sigmoid(z):
 return 1/(1+math.exp(-max(-30.,min(30.,z))))

def vector(context_row):
 return (1.,float(context_row["rest"]) / 4.,float(context_row["division"]),float(context_row["rivalry"]))

def logit(p):
 p=max(1e-6,min(1-1e-6,p))
 return math.log(p/(1-p))

def fitted_coefficients(rows,penalty=4.,steps=350):
 """L2 penalized logistic regression; baseline probability is fixed offset."""
 if not rows:
  raise ValueError("No training rows")
 weights=[0.]*4
 for _ in range(steps):
  gradient=[0.]*4
  for row in rows:
   x=row["features"]
   p=sigmoid(row["baseline_logit"]+sum(w*t for w,t in zip(weights,x)))
   for i in range(4):
    gradient[i]+=(p-row["actual"])*x[i]
  for i in range(4):
   ridge=0. if i==0 else penalty*weights[i]
   weights[i]-=0.4*(gradient[i]+ridge)/len(rows)
 return weights

def scores(rows,key):
 n=len(rows)
 if not n:return None
 return {"n":n,
         "brier":round(sum((r[key]-r["actual"])**2 for r in rows)/n,6),
         "log_loss":round(-sum(r["actual"]*math.log(max(1e-12,r[key]))+
                                 (1-r["actual"])*math.log(max(1e-12,1-r[key]))
                                 for r in rows)/n,6)}

def calibration(rows,key,bins=10):
 result=[]
 for k in range(bins):
  subset=[r for r in rows if min(bins-1,int(r[key]*bins))==k]
  result.append({"bin":k,"n":len(subset),
                 "mean_prediction":round(sum(r[key] for r in subset)/len(subset),6) if subset else None,
                 "observed_frequency":round(sum(r["actual"] for r in subset)/len(subset),6) if subset else None})
 return result

def evaluate(rows,start="2025-10-01",min_train=500):
 if len({r["game_id"] for r in rows})!=len(rows):
  raise ValueError("Duplicate games")
 prepared=timeline(rows,80,.5)
 ctx=context(rows)
 labels={r["game_id"]:r for r in rows}
 dataset=[]
 for item in prepared:
  source=labels[item["game_id"]]
  dataset.append({"game_id":item["game_id"],"date":item["date"],
                  "actual":int(source["ml_winner"]=="home"),
                  "baseline_logit":logit(item["probs"]["ml"][0]),
                  "baseline":item["probs"]["ml"][0],
                  "features":vector(ctx[item["game_id"]])})
 groups={}
 for row in dataset:groups.setdefault(row["date"],[]).append(row)
 history=[];tested=[];folds=[]
 for day in sorted(groups):
  batch=groups[day]
  if day>=start and len(history)>=min_train:
   coeff=fitted_coefficients(history)
   for row in batch:
    row["challenger"]=sigmoid(row["baseline_logit"]+sum(c*x for c,x in zip(coeff,row["features"])))
    tested.append(row)
   folds.append({"date":day,"training_n":len(history),
                 "n":len(batch),"coefficients":dict(zip(("intercept","rest_per_four_days","division","rivalry"),[round(x,6) for x in coeff]))})
  history.extend(batch) # freeze same-date training, no target-day outcome leakage
 if not tested:raise ValueError("Insufficient chronological test observations")
 baseline=scores(tested,"baseline");challenger=scores(tested,"challenger")
 return {"status":"research_trained_not_promoted",
         "method":"daily expanding-window L2 logistic offset, prior-date features",
         "minimum_training_samples":min_train,"test_start":start,
         "test_n":len(tested),"training_folds":len(folds),
         "latest_trained_coefficients":folds[-1]["coefficients"],
         "baseline":baseline,"challenger":challenger,
         "delta_brier":round(challenger["brier"]-baseline["brier"],6),
         "delta_log_loss":round(challenger["log_loss"]-baseline["log_loss"],6),
         "calibration":{"baseline":calibration(tested,"baseline"),
                        "challenger":calibration(tested,"challenger")},
         "feature_ablations_pending":True,
         "pp_pk_and_roster_coefficients":None,
         "holdout_previously_examined":True,"independent_prospective_validation":False,
         "official_model_unchanged":True,"odds_used":False,
         "predictions":[{"game_id":r["game_id"],"date":r["date"],
                          "actual_home_win":r["actual"],
                          "baseline_home_win":round(r["baseline"],6),
                          "challenger_home_win":round(r["challenger"],6)}
                         for r in tested]}

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--labels",required=True)
 parser.add_argument("--output",required=True)
 parser.add_argument("--start",default="2025-10-01")
 args=parser.parse_args()
 result=evaluate(read_labels(args.labels),start=args.start)
 dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k not in ("predictions","calibration")},indent=2))
if __name__=="__main__":main()
