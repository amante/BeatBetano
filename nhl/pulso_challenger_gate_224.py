"""Chronological training gate for PULSO NHL sporting challenger.

No fabricated historical as-of feature vectors. Block training until verified
point-in-time coverage and a genuine untouched later-date test cohort exist.
"""
import argparse,json
from collections import Counter
from pathlib import Path
from datetime import date

REQUIRED=("offense_skater_proxy","availability_delta_proxy","pp_bayes","pk_opponent_allowed_bayes","rest_days")
def audit(dataset,minimum_train=200,minimum_test=100):
 rows=dataset.get("rows",[])
 if dataset.get("status")!="training_dataset_research_only":raise ValueError("Verified research training dataset required")
 ids=set();dates=set()
 for row in rows:
  gid=str(row["game_id"])
  if gid in ids:raise ValueError("Duplicate fixture")
  ids.add(gid);dates.add(row["date"])
  if row.get("frozen_as_of","")[:10]>row["date"]:raise ValueError("Postgame/future feature snapshot")
  if not row.get("source_sha256"):raise ValueError("Unattested source")
  if set(row.get("features",{}))!={row["home"],row["away"]}:raise ValueError("Missing team features")
  for team in (row["home"],row["away"]):
   if any(row["features"][team].get(k) is None for k in REQUIRED):
    raise ValueError("Incomplete sporting vector")
 if not rows:return {"status":"blocked","reason":"no_verified_historical_asof_rows","n":0,"train":0,"test":0,"training_permitted":False}
 days=sorted(dates)
 # Date-ordered, non-overlapping holdout; with only one day no independent validation.
 cutoff=days[int(len(days)*0.8)] if len(days)>=5 else None
 train=[r for r in rows if cutoff and r["date"]<cutoff]
 test=[r for r in rows if cutoff and r["date"]>=cutoff]
 reasons=[]
 if not cutoff:reasons.append("insufficient_distinct_dates")
 if len(train)<minimum_train:reasons.append("insufficient_train_games")
 if len(test)<minimum_test:reasons.append("insufficient_holdout_games")
 return {"status":"ready_for_research_training" if not reasons else "blocked",
  "n":len(rows),"train":len(train),"test":len(test),"holdout_start":cutoff,
  "distinct_dates":len(days),"reasons":reasons,"training_permitted":not reasons,
  "official":False,"prediction_generated":False,
  "note":"No fitting or model promotion. Requires separately verified source timestamps and genuine walk-forward / baseline evaluation."}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--dataset",required=True);p.add_argument("--out",required=True)
 args=p.parse_args();result=audit(json.loads(Path(args.dataset).read_text()))
 path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
