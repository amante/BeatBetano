"""Holdout calibration diagnostics for every NHL outcome-only market, no promotion."""
import argparse,json
from collections import defaultdict
from pathlib import Path
from nhl.historical_target_walkforward import read_labels,CATEGORIES
from nhl.pulso_collective_calibration import run
from nhl.pulso_collective_audit_208 import rows_for_audit

def diagnostics(rows,min_bin=30):
 report={}
 for market,cats in CATEGORIES.items():
  classes={}
  for idx,cat in enumerate(cats):
   pairs=[(r["probs"][market][idx],int(r["y"][market]==cat)) for r in rows]
   # Equal-frequency bins avoid sparse probability deciles, but still gate on n.
   pairs.sort(key=lambda x:x[0])
   chunks=[pairs[i:i+max(min_bin,len(pairs)//10)] for i in range(0,len(pairs),max(min_bin,len(pairs)//10))]
   bins=[]
   for part in chunks:
    n=len(part);expected=sum(x for x,y in part)/n;realized=sum(y for x,y in part)/n
    bins.append({"n":n,"forecast_mean":round(expected,6),"observed_rate":round(realized,6),
      "absolute_gap":round(abs(expected-realized),6),"reliable_sample":n>=min_bin})
   classes[cat]={"bins":bins,"class_event_count":sum(y for p,y in pairs),
     "weighted_absolute_calibration_error":round(sum(b["n"]*b["absolute_gap"] for b in bins)/len(pairs),6)}
  monthly=defaultdict(list)
  for r in rows:
   actual=r["y"][market];probs=r["probs"][market]
   monthly[r["date"][:7]].append(sum((v-int(actual==cat))**2 for cat,v in zip(cats,probs))/len(cats))
  report[market]={"classes":classes,"monthly_brier":{m:{"n":len(x),"mean":round(sum(x)/len(x),6)} for m,x in sorted(monthly.items())}}
 return {"status":"research_only","n":len(rows),"markets":report,
  "limitations":["Equal-frequency reliability bins descriptive; not isotonic calibration","Historical outcome-only features; no current roster or goalie covariates","Minimum n per bin does not imply statistical significance"],"promotion":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--labels",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();rows=read_labels(a.labels);d=diagnostics(rows_for_audit(rows,run(rows)))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(d,indent=2));print(json.dumps({"n":d["n"],"markets":list(d["markets"])}))
if __name__=="__main__":main()
