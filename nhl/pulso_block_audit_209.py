"""Time-block paired uncertainty on frozen NHL historical holdout predictions."""
import argparse,json,math,random
from collections import defaultdict
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES,read_labels
from nhl.pulso_collective_calibration import run as train
from nhl.pulso_collective_audit_208 import rows_for_audit,brier,logloss,quantile

def evaluate(entries,blocks=7,replicates=1500,seed=209):
 if blocks<1 or replicates<100:raise ValueError("Invalid block settings")
 rng=random.Random(seed);result={}
 days=sorted({r["date"] for r in entries})
 if len(days)<blocks*2:raise ValueError("Too few days for temporal bootstrap")
 for target,cats in CATEGORIES.items():
  by_day=defaultdict(list)
  for r in entries:
   new=r["probs"][target];old=r["baseline_probs"][target];y=r["y"][target]
   by_day[r["date"]].append((brier(new,y,cats)-brier(old,y,cats),logloss(new,y,cats)-logloss(old,y,cats)))
  # Disjoint consecutive date blocks, same resampled dates for both competitors.
  chunks=[days[i:i+blocks] for i in range(0,len(days),blocks)]
  block_deltas=[[pair for day in chunk for pair in by_day[day]] for chunk in chunks]
  samples=[]
  for _ in range(replicates):
   selected=[block_deltas[rng.randrange(len(block_deltas))] for __ in chunks]
   pairs=[p for block in selected for p in block]
   samples.append(tuple(sum(x[j] for x in pairs)/len(pairs) for j in range(2)))
  actual=[x for block in block_deltas for x in block]
  ci={}
  for j,name in enumerate(("brier","log_loss")):
   observed=sum(v[j] for v in actual)/len(actual)
   lo,hi=[quantile([x[j] for x in samples],q) for q in (.025,.975)]
   ci[name]={"delta":round(observed,7),"block_ci95":[round(lo,7),round(hi,7)],
    "favorable_excludes_zero":bool(hi<0)}
  by_month=defaultdict(list)
  for r in entries:
   y=r["y"][target];by_month[r["date"][:7]].append(brier(r["probs"][target],y,cats)-brier(r["baseline_probs"][target],y,cats))
  result[target]={"n":len(actual),"consecutive_calendar_day_block_size":blocks,
   "confidence":ci,"monthly_brier_delta":{k:round(sum(v)/len(v),7) for k,v in sorted(by_month.items())}}
 return {"status":"research_only","n":len(entries),"method":"nonoverlapping 7-day block bootstrap of paired model differences",
  "seed":seed,"replicates":replicates,"markets":result,
  "caveats":["Calendar blocks are not a full team-dependence correction","Five markets tested; no multiple-testing-adjusted promotion","No historical as-of skater, goalie or CRS features"],
  "official":False,"automatic_promotion":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--labels",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();rows=read_labels(a.labels);result=evaluate(rows_for_audit(rows,train(rows)))
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:{"brier":v["confidence"]["brier"],"log_loss":v["confidence"]["log_loss"]} for k,v in result["markets"].items()},indent=2))
if __name__=="__main__":main()
