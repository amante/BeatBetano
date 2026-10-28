"""NHL ML robustness audit: context baseline, paired date bootstrap, monthly stability.

Candidate coefficients fixed from prior tuning experiment; context fitted only on tune.
This is research, not validated official NHL model or a production adjustment.
"""
import argparse,json,math,random,statistics,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START
from prior_stats_ml_ablations import prepare,probability
from schedule_context_ablations import context,adjust,scoring

GOALIE=-4.;SKATER=.2
GRID=(-.06,-.03,0.,.03,.06)
def loss(p,y):
    p=max(1e-12,min(1-1e-12,p))
    return (p-y)**2,-(y*math.log(p)+(1-y)*math.log(1-p))
def rows_by_date(predictions,contextual,features,c):
    out=[]
    for r in predictions:
        gid=r["game_id"];baseline=r["probs"]["ml"][0];ctx=adjust(baseline,contextual[gid],c)
        mixed=probability(ctx,features[gid],{"goalie":GOALIE,"skater":SKATER})
        y=int(r["y"]["ml"]=="home")
        out.append({"date":r["date"],"id":gid,"baseline":loss(baseline,y),
          "context":loss(ctx,y),"combined":loss(mixed,y)})
    return out
def means(items,name):
    return {"n":len(items),"brier":round(statistics.mean(x[name][0] for x in items),6),
        "log_loss":round(statistics.mean(x[name][1] for x in items),6)}
def intervals(rows,reference,candidate,samples=2000,seed=20261027):
    bydate=defaultdict(list)
    for r in rows:bydate[r["date"]].append(r)
    days=sorted(bydate)
    if len(days)<15:raise ValueError("Too few dates for cluster bootstrap")
    rng=random.Random(seed)
    averages=[]
    for _ in range(samples):
        sample=[g for _ in days for g in bydate[rng.choice(days)]]
        averages.append(tuple(statistics.mean(x[candidate][i]-x[reference][i] for x in sample) for i in (0,1)))
    def bounds(index):
        values=sorted(x[index] for x in averages)
        return [round(values[int(.025*samples)],6),round(values[min(samples-1,int(.975*samples))],6)]
    return {"resamples":samples,"seed":seed,"unit":"calendar-date cluster",
        "delta_brier_95pct_interval":bounds(0),"delta_log_loss_95pct_interval":bounds(1),
        "favorable_brier_resample_rate":round(sum(v[0]<0 for v in averages)/samples,4)}
def evaluate(labels,records):
    evidence=prepare(labels,records)
    rows=timeline(labels,80,.5);ctx=context(labels)
    tune=[r for r in rows if TUNE_START<=r["date"]<=TUNE_END]
    hold=[r for r in rows if r["date"]>=TEST_START]
    if len(tune)<200 or len(hold)!=554:raise ValueError("Sealed holdout mismatch")
    choices=[(r,d,v) for r in GRID for d in GRID for v in GRID]
    best=min(choices,key=lambda c:(scoring(tune,ctx,c)["log_loss"],c))
    result=rows_by_date(hold,ctx,evidence,best)
    grouped=defaultdict(list)
    for r in result:grouped[r["date"][:7]].append(r)
    monthly={day:{key:means(items,key) for key in ("baseline","context","combined")} for day,items in sorted(grouped.items())}
    return {"source_games":len(labels),"holdout_games":len(result),"test_from":TEST_START,
      "tune_window":[TUNE_START,TUNE_END],"context_coefficients":list(best),
      "fixed_prior_experimental_coefficients":{"goalie":GOALIE,"skater":SKATER},
      "holdout":{k:means(result,k) for k in ("baseline","context","combined")},
      "paired_delta_combined_minus_context":intervals(result,"context","combined"),
      "paired_delta_combined_minus_baseline":intervals(result,"baseline","combined"),
      "monthly_stability":monthly,
      "caveats":["Previous experiments already inspected same sealed holdout; therefore this is NOT an independent second confirmation.",
      "Goalie coefficient on tuning boundary with counterintuitive sign; no automatic promotion.",
      "Team-level historical goalie save% is not a known pregame starter.",
      "Context parameters chosen on tune only; fixed goalie/skater coefficients from earlier tune."],
      "official_model_promoted":False,"odds_used":False}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--labels",required=True);ap.add_argument("--features",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();r=evaluate(read_labels(a.labels),json.loads(Path(a.features).read_text()))
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2))
    print(json.dumps(r,indent=2))
if __name__=="__main__":main()
