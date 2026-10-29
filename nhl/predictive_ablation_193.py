"""NHL #193: date-frozen, expanding-month feature ablations.

Research only: coefficients are fitted on strictly earlier months. All variants
score precisely the same games. No selection on evaluated months, no odds,
and no claims of independent prospective validation.
"""
import argparse,json
from pathlib import Path
try:
 from nhl.historical_target_walkforward import read_labels,timeline
 from nhl.integrated_ablation_audit_186 import context
 from nhl.trained_context_192 import fitted_coefficients,sigmoid,logit,scores,calibration,vector
except ModuleNotFoundError:
 from historical_target_walkforward import read_labels,timeline
 from integrated_ablation_audit_186 import context
 from trained_context_192 import fitted_coefficients,sigmoid,logit,scores,calibration,vector

VARIANTS={
 "baseline":(),
 "rest_only":(1,),
 "division_only":(2,),
 "rivalry_only":(3,),
 "rest_division":(1,2),
 "rest_rivalry":(1,3),
 "division_rivalry":(2,3),
 "all_three":(1,2,3),
}
COEFFICIENTS=("intercept","rest_per_four_days","division","rivalry")

def fit_variant(training,active,penalty=4.):
 if not active:return [0.]*4
 columns=(0,)+tuple(active)
 slim=[{"features":tuple(row["features"][i] for i in columns),
        "baseline_logit":row["baseline_logit"],"actual":row["actual"]} for row in training]
 fitted=fitted_coefficients(slim,penalty=penalty,steps=250)
 weights=[0.]*4
 for col,value in zip(columns,fitted):weights[col]=value
 return weights

def evaluate(rows,start="2025-10-01",minimum_training=500):
 if len({r["game_id"] for r in rows})!=len(rows):raise ValueError("Duplicate game IDs")
 prepared=timeline(rows,80,.5)
 contexts=context(rows)
 labels={r["game_id"]:r for r in rows}
 data=[]
 for row in prepared:
  data.append({"game_id":row["game_id"],"date":row["date"],
    "actual":int(labels[row["game_id"]]["ml_winner"]=="home"),
    "features":vector(contexts[row["game_id"]]),
    "baseline":row["probs"]["ml"][0],
    "baseline_logit":logit(row["probs"]["ml"][0])})
 months={}
 for row in data:months.setdefault(row["date"][:7],[]).append(row)
 train=[];predictions=[];fitted_history=[]
 for month in sorted(months):
  batch=months[month]
  if batch[0]["date"]>=start and len(train)>=minimum_training:
   weights={name:fit_variant(train,active) for name,active in VARIANTS.items()}
   for row in batch:
    output={"game_id":row["game_id"],"date":row["date"],"actual":row["actual"],"baseline":row["baseline"]}
    for name,w in weights.items():
     output[name]=sigmoid(row["baseline_logit"]+sum(a*b for a,b in zip(w,row["features"])))
    predictions.append(output)
   fitted_history.append({"month":month,"train_n":len(train),
       "coefficients":{name:dict(zip(COEFFICIENTS,[round(x,6) for x in w]))
                       for name,w in weights.items()}})
  train.extend(batch) # freeze entire test month before adding any of its results
 if not predictions:raise ValueError("Insufficient strictly earlier training history")
 control=scores(predictions,"baseline")
 comparisons={}
 for name in VARIANTS:
  metric=scores(predictions,name)
  coefficients=[f["coefficients"][name] for f in fitted_history]
  comparisons[name]={"scores":metric,
    "delta_brier":round(metric["brier"]-control["brier"],6),
    "delta_log_loss":round(metric["log_loss"]-control["log_loss"],6),
    "latest_coefficients":coefficients[-1],
    "coefficient_ranges":{k:{"minimum":min(c[k] for c in coefficients),
                              "maximum":max(c[k] for c in coefficients),
                              "positive_months":sum(c[k]>0 for c in coefficients),
                              "negative_months":sum(c[k]<0 for c in coefficients)}
                          for k in COEFFICIENTS if k=="intercept" or COEFFICIENTS.index(k) in VARIANTS[name]},
    "calibration":calibration(predictions,name)}
 return {"status":"research_only_not_promoted",
   "method":"expanding-window monthly refit; evaluated month entirely held out",
   "training_cutoff":"all training dates strictly earlier than scored month",
   "minimum_training":minimum_training,"test_start":start,
   "n":len(predictions),"evaluated_months":len(fitted_history),
   "baseline":control,"comparisons":comparisons,
   "coefficient_history":fitted_history,"predictions":predictions,
   "selection_on_test":False,"previously_inspected_archive":True,
   "independent_prospective_validation":False,
   "pp_pk_and_roster_not_evaluable":True,"official_model_unchanged":True,"odds_used":False}

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--labels",required=True)
 parser.add_argument("--output",required=True)
 args=parser.parse_args()
 result=evaluate(read_labels(args.labels))
 dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"n":result["n"],"evaluated_months":result["evaluated_months"],
    "comparisons":{k:{"scores":v["scores"],"delta_brier":v["delta_brier"],
    "delta_log_loss":v["delta_log_loss"],"latest_coefficients":v["latest_coefficients"]}
      for k,v in result["comparisons"].items()}},indent=2))
if __name__=="__main__":main()
