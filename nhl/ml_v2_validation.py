"""ML v2: chronological parameter selection and untouched future test."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from walkforward_calibration import ml

TRAIN_END="2025-06-30"
TUNE_START="2025-10-01"
TUNE_END="2026-02-28"
TEST_START="2026-03-01"

def features(rows):
    # Historical goals from earlier dates only; reset team form at season
    # boundary to avoid carrying obsolete roster form between seasons.
    grouped=defaultdict(list)
    for r in rows:grouped[r["date"]].append(r)
    states=defaultdict(lambda:[0,0,0])
    season=None
    result=[]
    for day in sorted(grouped):
        cycle=day[:4] if int(day[5:7])>=7 else str(int(day[:4])-1)
        if cycle!=season:
            states=defaultdict(lambda:[0,0,0]);season=cycle
        for g in grouped[day]:
            home=states[g["home"]][:];away=states[g["away"]][:]
            result.append({"date":day,"id":g["id"],"y":int(g["hg"]>g["ag"]),
                           "home":home,"away":away})
        for g in grouped[day]:
            h=states[g["home"]];a=states[g["away"]]
            h[0]+=g["hg"];h[1]+=g["ag"];h[2]+=1
            a[0]+=g["ag"];a[1]+=g["hg"];a[2]+=1
    return result

def probability(row,prior,home_log,shrink):
    h,a=row["home"],row["away"]
    h_for=(h[0]+shrink*prior)/(h[2]+shrink)
    a_against=(a[1]+shrink*prior)/(a[2]+shrink)
    a_for=(a[0]+shrink*prior)/(a[2]+shrink)
    h_against=(h[1]+shrink*prior)/(h[2]+shrink)
    return ml(max(.2,min(8,(h_for+a_against)/2*math.exp(home_log/2))),
              max(.2,min(8,(a_for+h_against)/2*math.exp(-home_log/2))))

def evaluate(rows,params):
    preds=[(probability(r,*params),r["y"]) for r in rows]
    n=len(preds)
    if n==0:raise ValueError("Empty period")
    return {"n":n,"brier":round(sum((p-y)**2 for p,y in preds)/n,6),
      "log_loss":round(-sum(y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p)) for p,y in preds)/n,6),
      "predicted_home":round(sum(p for p,_ in preds)/n,4),
      "observed_home":round(sum(y for _,y in preds)/n,4)}

def run(rows):
    prepared=features(rows)
    train=[r for r in prepared if r["date"]<=TRAIN_END]
    tune=[r for r in prepared if TUNE_START<=r["date"]<=TUNE_END]
    test=[r for r in prepared if r["date"]>=TEST_START]
    if len(train)<1000 or len(tune)<300 or len(test)<80:
        raise ValueError("Chronological partitions lack sufficient samples")
    grid=[(prior,home,shrink) for prior in (2.8,3.0,3.2)
          for home in (-.08,0,.04,.08,.12,.16) for shrink in (5,10,20)]
    choices=sorted([(evaluate(tune,params)["log_loss"],params) for params in grid],
                   key=lambda x:(x[0],x[1]))
    selected=choices[0][1]
    benchmark=(3.,0.,5.)
    baseline=round(sum((.5-r["y"])**2 for r in test)/len(test),6)
    v2=evaluate(test,selected)
    reference=evaluate(test,benchmark)
    return {"partition":{"train_through":TRAIN_END,"tune_start":TUNE_START,
       "tune_through":TUNE_END,"untouched_test_from":TEST_START},
      "selection":"lowest log loss on tune only","selected":{"prior_goals":selected[0],
       "home_log_adjustment":selected[1],"shrink_games":selected[2]},
      "tune_metrics":evaluate(tune,selected),"test_candidate":v2,
      "test_goals_only_reference":reference,"neutral_brier":baseline,
      "test_season_segments":{year:{"candidate":evaluate([r for r in test if r["date"][:4]==year],selected),
        "reference":evaluate([r for r in test if r["date"][:4]==year],benchmark)}
          for year in sorted(set(r["date"][:4] for r in test))},
      "promotion_authorized":False,
      "limitation":"Result-only goal process; not historical full PR132 model; test period begins March 2026."}

def markdown(r):
    c=r["test_candidate"];b=r["test_goals_only_reference"]
    return ("## NHL ML v2 — train/tune/test separation\n\n"
      f"Training prior period through {TRAIN_END}; parameter selection {TUNE_START} to {TUNE_END}; untouched test from {TEST_START}.\n\n"
      f"Selected: {r['selected']}\n\n"
      "| Model | Test N | Brier ↓ | Log Loss ↓ | Avg P(home) | Home actual |\n"
      "|---|---:|---:|---:|---:|---:|\n"
      f"| ML v2 | {c['n']} | {c['brier']} | {c['log_loss']} | {c['predicted_home']} | {c['observed_home']} |\n"
      f"| Goals-only reference | {b['n']} | {b['brier']} | {b['log_loss']} | {b['predicted_home']} | {b['observed_home']} |\n\n"
      f"Temporal segments: {json.dumps(r['test_season_segments'])}\n\n"
      "**No automatic promotion, and no full-factor NHL validation.**\n")

def main():
    ap=argparse.ArgumentParser()
    for name in ("history","output","summary"):ap.add_argument("--"+name,required=True)
    args=ap.parse_args()
    report=run(json.loads(Path(args.history).read_text()))
    for path,contents in ((args.output,json.dumps(report,indent=2)),(args.summary,markdown(report))):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(contents)
    print(json.dumps(report))
if __name__=="__main__":main()
