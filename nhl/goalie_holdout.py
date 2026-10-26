"""NHL goalie impact: leakage-safe chronological ridge challenger on frozen features.

This evaluator never promotes itself to official; source coverage and all
prospective lineup verifications must be reviewed separately.
"""
import argparse,json,math
from datetime import datetime,timezone
from pathlib import Path

FEATURES=("goalie_sv_recent","goalie_starts_7d","opponent_goal_diff_prior",
          "team_goal_diff_prior","defense_goals_against_prior")
def timestamp(x):
 d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timezone required")
 return d.astimezone(timezone.utc)
def sigmoid(x):
 return 1/(1+math.exp(-max(-30,min(30,x))))
def logit(p):return math.log(p/(1-p))
def validate(rows):
 if not isinstance(rows,list) or not rows:raise ValueError("Frozen rows required")
 seen=set();ordered=[]
 for r in rows:
  gid=str(r["event_id"])
  if gid in seen:raise ValueError("Duplicate event")
  seen.add(gid)
  if r.get("sport")!="nhl" or r.get("market")!="moneyline" or r.get("odds_used") is not False:
   raise ValueError("Only odds-free NHL moneyline")
  freeze=timestamp(r["prediction_as_of_utc"]);tip=timestamp(r["tipoff_utc"])
  if not timestamp(r["latest_feature_observed_at_utc"])<=freeze<tip:
   raise ValueError("Leakage or no pregame snapshot")
  if r.get("sources_verified") is not True or r.get("starter_confirmed_at_freeze") is not True:
   raise ValueError("Missing verified evidence")
  base=r.get("baseline_p_home");y=r.get("home_won")
  if type(base) not in (float,int) or not .001<=base<=.999 or type(y) is not int or y not in (0,1):
   raise ValueError("Invalid baseline/outcome")
  vals=[]
  for key in FEATURES:
   value=r.get(key)
   if type(value) not in (int,float) or not math.isfinite(value):raise ValueError("Missing/nonfinite feature "+key)
   vals.append(float(value))
  ordered.append((tip,gid,base,y,vals))
 ordered.sort()
 return ordered
def fit(train,alpha=10.,iterations=200):
 if len(train)<30:raise ValueError("Insufficient training")
 # Center and scale strictly using training samples, not the future holdout.
 mean=[sum(x[4][j] for x in train)/len(train) for j in range(len(FEATURES))]
 std=[max(1e-6,(sum((x[4][j]-mean[j])**2 for x in train)/len(train))**.5) for j in range(len(FEATURES))]
 weights=[0.]*(len(FEATURES)+1)
 for _ in range(iterations):
  grad=[0.]*len(weights)
  for _,_,base,y,vec in train:
   xs=[1.]+[(vec[j]-mean[j])/std[j] for j in range(len(FEATURES))]
   pred=sigmoid(logit(base)+sum(w*v for w,v in zip(weights,xs)))
   for j,v in enumerate(xs):grad[j]+=(pred-y)*v
  for j in range(len(weights)):
   grad[j]+=(alpha*weights[j] if j else 0)
   weights[j]-=.15*grad[j]/len(train)
 return weights,mean,std
def measure(pairs):
 n=len(pairs)
 return {"n":n,"brier":sum((p-y)**2 for p,y in pairs)/n,
         "log_loss":-sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y in pairs)/n}
def walk_forward(rows,min_train=200,min_test=50):
 ordered=validate(rows)
 years=sorted({row[0].year for row in ordered})
 results=[]
 for year in years:
  train=[r for r in ordered if r[0].year<year]
  test=[r for r in ordered if r[0].year==year]
  if len(train)<min_train or len(test)<min_test:continue
  weights,mean,std=fit(train)
  base=[];challenger=[]
  for _,_,p,y,x in test:
   vec=[1.]+[(x[j]-mean[j])/std[j] for j in range(len(FEATURES))]
   adjusted=sigmoid(logit(p)+sum(w*v for w,v in zip(weights,vec)))
   base.append((p,y));challenger.append((adjusted,y))
  a=measure(base);b=measure(challenger)
  results.append({"test_year":year,"train_n":len(train),"baseline":a,
   "goalie_challenger":b,"brier_gain":a["brier"]-b["brier"],
   "log_loss_gain":a["log_loss"]-b["log_loss"],
   "weights":dict(zip(("intercept",)+FEATURES,weights)),
   "training_only_standardization":True})
 return {"sport":"nhl","market":"moneyline","features":list(FEATURES),
  "holdout_results":results,"passed_independent_validation":False,
  "authorized_for_final_probability":False,
  "note":"Calendar-year holdout diagnostic only; validate per-season, independent audit and causality limits before production."}
def main():
 p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True)
 a=p.parse_args()
 report=walk_forward(json.loads(Path(a.input).read_text()))
 target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(report,indent=2))
 print(json.dumps({"holdout_windows":len(report["holdout_results"]),"validated":False}))
if __name__=="__main__":main()
