"""NHL schedule-only context ablations on sealed historical ML holdout.

Only fixture identities/date and previously completed game dates are read.
Context coefficients are selected solely on pre-holdout tuning data.
No odds, postgame player statistics, retrospective injuries or goalie starts.
"""
import argparse,json,math,sys
from collections import defaultdict
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START
from all_module_historical_audit import DIV,RIVALS

def context(rows):
    days=defaultdict(list)
    for r in rows:days[r["date"]].append(r)
    last={};out={}
    for day in sorted(days):
        today=date.fromisoformat(day)
        for g in days[day]:
            h,a=g["home"],g["away"]
            hr=(today-last[h]).days-1 if h in last else None
            ar=(today-last[a]).days-1 if a in last else None
            # Cap rest to prevent extraordinary offseason gaps dominating.
            differential=max(-4,min(4,hr-ar)) if hr is not None and ar is not None else 0
            out[g["game_id"]]={"rest":differential,
                "division":int(DIV.get(h) is not None and DIV[h]==DIV.get(a)),
                "rivalry":int(frozenset((h,a)) in RIVALS),
                "rest_known":hr is not None and ar is not None}
        for g in days[day]:
            last[g["home"]]=today;last[g["away"]]=today
    return out

def adjust(p,ctx,coefficients):
    x=math.log(max(1e-8,p)/max(1e-8,1-p))
    x+=coefficients[0]*ctx["rest"]
    x+=coefficients[1]*ctx["division"]
    x+=coefficients[2]*ctx["rivalry"]
    return 1/(1+math.exp(-max(-30,min(30,x))))

def scoring(predictions,contexts,coefficients):
    n=len(predictions)
    if not n:raise ValueError("Empty partition")
    b=ll=0.
    for r in predictions:
        p=adjust(r["probs"]["ml"][0],contexts[r["game_id"]],coefficients)
        y=int(r["y"]["ml"]=="home")
        b+=(p-y)**2
        ll-=y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p))
    return {"n":n,"brier":round(b/n,6),"log_loss":round(ll/n,6)}

def compute(rows):
    base=timeline(rows,80,.5)
    contexts=context(rows)
    tune=[r for r in base if TUNE_START<=r["date"]<=TUNE_END]
    test=[r for r in base if r["date"]>=TEST_START]
    if len(tune)<200 or len(test)<100:raise ValueError("Insufficient chronological windows")
    grid=(-.06,-.03,0.,.03,.06)
    configurations={
       "baseline":[(0.,0.,0.)],
       "rest_only":[(r,0.,0.) for r in grid],
       "division_only":[(0.,d,0.) for d in grid],
       "rivalry_only":[(0.,0.,v) for v in grid],
       "rest_division_rivalry":[(r,d,v) for r in grid for d in grid for v in grid]
    }
    results={}
    for name,choices in configurations.items():
        best=min(choices,key=lambda c:(scoring(tune,contexts,c)["log_loss"],c))
        results[name]={"tune":scoring(tune,contexts,best),
                       "holdout":scoring(test,contexts,best),
                       "coefficients":list(best)}
    return {"data":"NHL official audited 2811 postgame labels",
      "train_feature_policy":"fixture metadata and team prior fixture dates only",
      "test_from":TEST_START,"test_n":len(test),
      "tune_range":[TUNE_START,TUNE_END],
      "baseline_params":{"shrink":80,"team_weight":.5,"source":"NHL first benchmark tuned on preholdout data"},
      "ablations":results,"odds_used":False,"official_model_rated":False,
      "promotion_authorized":False,
      "warning":"Exploratory additive-context ablation only; schedule information is limited to recorded game dates; not an official 14-module challenger."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=compute(read_labels(a.labels))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
