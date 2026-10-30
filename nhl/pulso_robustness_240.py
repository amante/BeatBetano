"""Research-only paired ML uncertainty: bootstrap resamples whole fixture dates."""
import argparse,csv,json,math,random
from collections import defaultdict
from pathlib import Path
from nhl.pulso_sporting_benchmark_239 import outcome_baseline,score,reliability

def quantify(challenger,labels,iterations=2000,seed=240):
 if challenger.get("status")!="research_only_challenger_fitted" or challenger.get("promoted") is not False:
  raise ValueError("Unverified research challenger")
 forecasts=challenger.get("holdout_predictions",[])
 if len(forecasts)!=challenger.get("holdout_games") or not forecasts:raise ValueError("Unverified holdout count")
 ids=[str(f["game_id"]) for f in forecasts]
 if len(set(ids))!=len(ids):raise ValueError("Duplicate predictions")
 baseline=outcome_baseline(labels,set(ids))
 grouped=defaultdict(list);years=defaultdict(list)
 for f in forecasts:
  ref=baseline[str(f["game_id"])]
  if f["date"]!=ref["date"] or f["date"]<challenger["holdout_start"] or f["actual_home_ml"]!=ref["y"]:
   raise ValueError("Fixture/date/target mismatch")
  y=ref["y"];cp=f["p_home_ml"];bp=ref["p_home_ml"]
  if any(isinstance(p,bool) or not isinstance(p,(float,int)) or not math.isfinite(p) or not 0<=p<=1 for p in (cp,bp)):
   raise ValueError("Invalid probabilities")
  row=(cp,bp,y)
  grouped[f["date"]].append(row);years[f["date"][:4]].append(row)
 if len(grouped)<10:raise ValueError("Insufficient distinct holdout dates")
 if iterations<200:raise ValueError("Insufficient bootstrap repetitions")
 def diff(rows,method):
  def loss(p,y):
   if method=="brier":return (p-y)**2
   return -(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)))
  return sum(loss(c,y)-loss(b,y) for c,b,y in rows)/len(rows)
 dates=sorted(grouped)
 samples={k:[] for k in ("brier","log_loss")}
 rng=random.Random(seed)
 for _ in range(iterations):
  sampled=[row for _ in dates for row in grouped[rng.choice(dates)]]
  for metric in samples:samples[metric].append(diff(sampled,metric))
 def interval(a):
  ordered=sorted(a);n=len(ordered)
  return [round(ordered[int((n-1)*.025)],7),round(ordered[int((n-1)*.975)],7)]
 all_rows=[row for d in dates for row in grouped[d]]
 stats={}
 for metric,distribution in samples.items():
  bounds=interval(distribution)
  stats[metric]={"delta":round(diff(all_rows,metric),7),
   "paired_date_cluster_bootstrap_ci95":bounds,
   "fraction_resamples_challenger_better":round(sum(x<0 for x in distribution)/len(distribution),6),
   "excludes_zero":bounds[1]<0 or bounds[0]>0}
 return {"status":"research_robustness_completed","paired_games":len(all_rows),
  "holdout_dates":len(dates),"bootstrap_repetitions":iterations,"bootstrap_seed":seed,
  "scores":{"challenger":score([(c,y) for c,b,y in all_rows]),
    "baseline":score([(b,y) for c,b,y in all_rows])},
  "uncertainty":stats,
  "by_year":{yr:{"n":len(rows),"delta_brier":round(diff(rows,"brier"),7),
    "delta_log_loss":round(diff(rows,"log_loss"),7)} for yr,rows in sorted(years.items())},
  "calibration":{"challenger":reliability([(c,y) for c,b,y in all_rows]),
    "baseline":reliability([(b,y) for c,b,y in all_rows])},
  "decision":{"production_baseline":"retain_experimental_outcome_only_baseline",
   "challenger_promotion_allowed":False,
   "reason":"Single retrospective fixed holdout; bootstrap is sensitivity, not independent prospective replication. No lineup/goalie/PP evidence."},
  "official":False,"odds_used":False,"auto_promoted":False,
  "limitations":"Cluster bootstrap on holdout dates only; overlapping training windows and historical regime drift not independently quantified."}

def main():
 p=argparse.ArgumentParser()
 for key in ("challenger","labels","out"):p.add_argument("--"+key,required=True)
 a=p.parse_args()
 with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
 result=quantify(json.loads(Path(a.challenger).read_text()),labels)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:result[k] for k in ("paired_games","holdout_dates","scores","uncertainty","decision")},indent=2))
if __name__=="__main__":main()
