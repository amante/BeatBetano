"""PR208: reproducible holdout uncertainty, calibration, ablation and frozen pregame ledger."""
import argparse,hashlib,json,math,random
from collections import defaultdict
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES,TEST_START,timeline,read_labels
from nhl.pulso_collective_calibration import run as baseline_run
from nhl.pulso_pregame_v7 import parse_utc

def rows_for_audit(rows,parameters):
 chosen=parameters["selected_hyperparameters"]
 baseline=timeline(rows,20,0.)
 cache={}
 for v in chosen.values():
  key=(v["shrink"],v["team_weight"])
  if key not in cache:cache[key]=timeline(rows,*key)
 return [{**r,"probs":{t:cache[(v["shrink"],v["team_weight"])][i]["probs"][t] for t,v in chosen.items()},
   "baseline_probs":baseline[i]["probs"]} for i,r in enumerate(baseline) if r["date"]>=TEST_START]

def brier(p,y,cats):
 return sum((v-float(c==y))**2 for c,v in zip(cats,p))/len(cats)
def logloss(p,y,cats):
 return -math.log(max(1e-12,p[cats.index(y)]))
def quantile(xs,q):
 xs=sorted(xs);pos=(len(xs)-1)*q;lo=int(pos);hi=min(lo+1,len(xs)-1)
 return xs[lo]+(xs[hi]-xs[lo])*(pos-lo)
def audit(rows,seed=208,bootstrap=1000):
 if not rows:raise ValueError("No holdout rows")
 out={}; rng=random.Random(seed)
 for target,cats in CATEGORIES.items():
  records=[];bins=defaultdict(list)
  for r in rows:
   y=r["y"][target];new=r["probs"][target];old=r["baseline_probs"][target]
   if len(new)!=len(cats) or len(old)!=len(cats):raise ValueError("Probability shape mismatch")
   values=(brier(new,y,cats)-brier(old,y,cats),logloss(new,y,cats)-logloss(old,y,cats))
   records.append(values)
   # Calibration of the realized class probability is NOT an appropriate binning
   # target; one-vs-rest bins per possible outcome avoid label leakage.
   for i,c in enumerate(cats):
    p=new[i];binid=min(9,int(p*10))
    bins[(c,binid)].append((p,float(y==c)))
  n=len(records)
  sampling=[]
  for _ in range(bootstrap):
   idx=[rng.randrange(n) for __ in range(n)]
   sampling.append(tuple(sum(records[i][j] for i in idx)/n for j in (0,1)))
  ci={}
  for j,metric in enumerate(("brier","log_loss")):
   mean=sum(r[j] for r in records)/n
   ci[metric]={"delta":round(mean,7),"ci95":[round(quantile([x[j] for x in sampling],q),7) for q in (.025,.975)],
    "bootstrap_method":"paired game resampling; ignores temporal/team dependence"}
  calibration={c:[{"bin":i,"n":len(bins[(c,i)]),
      "predicted":round(sum(p for p,y in bins[(c,i)])/len(bins[(c,i)]),6) if bins[(c,i)] else None,
      "observed":round(sum(y for p,y in bins[(c,i)])/len(bins[(c,i)]),6) if bins[(c,i)] else None} for i in range(10)] for c in cats}
  out[target]={"n":n,"uncertainty":ci,"one_vs_rest_reliability_bins":calibration}
 return {"holdout_n":len(rows),"seed":seed,"replicates":bootstrap,"markets":out,
  "ablation":{"historical_global_only":"baseline","historical_team_role":"challenger",
   "player_goalie_crs_pp_pk":"not_evaluable_missing_asof_features"},
  "caveat":"Bootstrap CIs are descriptive; dependence and selection uncertainty require stronger validation.",
  "odds_used_in_model":False,"automatic_promotion":False}

def freeze_prediction(record):
 required=("game_id","start_utc","prediction_as_of_utc","source_asof_utc","source_url","model_version","market","probabilities")
 if any(k not in record for k in required):raise ValueError("Missing ledger evidence")
 start=parse_utc(record["start_utc"]);issued=parse_utc(record["prediction_as_of_utc"]);source=parse_utc(record["source_asof_utc"])
 if source>issued or issued>=start:raise ValueError("Out-of-order or postgame evidence")
 if not str(record["source_url"]).startswith("https://"):raise ValueError("Unsourced prediction")
 if record.get("odds_used_in_model") is not False:raise ValueError("Odds involvement not excluded")
 if record.get("point_in_time_sources_verified") is not True:raise ValueError("Source verification absent")
 if record["market"] not in CATEGORIES:raise ValueError("Unknown market")
 cats=CATEGORIES[record["market"]];probs=record["probabilities"]
 if not isinstance(probs,dict) or set(probs)!=set(cats) or any(type(probs[c]) not in (int,float) or not math.isfinite(probs[c]) or probs[c]<0 or probs[c]>1 for c in cats):raise ValueError("Invalid probabilities")
 if abs(sum(probs.values())-1)>1e-6:raise ValueError("Not normalized")
 encoded=json.dumps(record,sort_keys=True,separators=(",",":")).encode()
 return {"record":record,"sha256":hashlib.sha256(encoded).hexdigest(),"frozen":True,
  "note":"Evidence signature only; immutable storage must be provided externally."}

def main():
 p=argparse.ArgumentParser();p.add_argument("--labels",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();rows=read_labels(a.labels);trained=baseline_run(rows)
 result=audit(rows_for_audit(rows,trained));out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2));print(json.dumps({"holdout":result["holdout_n"],"markets":list(result["markets"]) }))
if __name__=="__main__":main()
