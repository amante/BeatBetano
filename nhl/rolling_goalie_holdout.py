"""Tune rolling goalie adjustments on historical tune dates; report holdout by phase.

Exploratory follow-up on previously inspected holdout. No model promotion.
"""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START
from schedule_context_ablations import context,adjust,scoring
from season_phase_goalie_audit import phase_counts

def fit(labels,features):
    source={str(x["game_id"]):x for x in features}
    if len(features)!=len(labels) or len(source)!=len(labels):raise ValueError("Incomplete rolling features")
    for r in labels:
        x=source.get(r["game_id"])
        if not x or x["date"]!=r["date"] or x["source_class"]!="previous_date_goalie_team_observations":
            raise ValueError("Misaligned features")
    rows=timeline(labels,80,.5);cx=context(labels);phase=phase_counts(labels)
    train=[r for r in rows if TUNE_START<=r["date"]<=TUNE_END]
    hold=[r for r in rows if r["date"]>=TEST_START]
    if len(hold)!=554:raise ValueError("Unexpected holdout")
    grid=(-.06,-.03,0.,.03,.06)
    c=min(((a,b,d) for a in grid for b in grid for d in grid),key=lambda v:(scoring(train,cx,v)["log_loss"],v))
    def predict(r,window,coef,shrink):
        x=source[r["game_id"]];base=adjust(r["probs"]["ml"][0],cx[r["game_id"]],c)
        if window is None:return base
        name=f"goalie_last_{window}"
        h=x["home"][name]["shrunk_save_pct" if shrink else "save_pct"]
        a=x["away"][name]["shrunk_save_pct" if shrink else "save_pct"]
        if h is None or a is None:return base
        z=math.log(base/(1-base))+coef*(h-a)
        return 1/(1+math.exp(-max(-30,min(30,z))))
    def score(group,params):
        losses=[]
        for r in group:
            p=predict(r,*params);y=int(r["y"]["ml"]=="home")
            losses.append(((p-y)**2,-math.log(max(1e-12,p if y else 1-p))))
        if not losses:return {"n":0,"brier":None,"log_loss":None}
        return {"n":len(losses),"brier":round(sum(x[0] for x in losses)/len(losses),6),
                "log_loss":round(sum(x[1] for x in losses)/len(losses),6)}
    # Constrain goalie coefficient sign to be non-negative for physical interpretability.
    candidates=[(w,k,s) for w in (3,5,10) for k in (0.,1.,2.,4.) for s in (False,True)]
    best=min(candidates,key=lambda v:(score(train,v)["log_loss"],v))
    groups={}
    for name in ("opening_1_10","developing_11_25","established_26_plus","mixed"):
        part=[r for r in hold if phase[r["game_id"]]["both_phase"]==name]
        groups[name]={"context":score(part,(None,0.,False)),"selected":score(part,best)}
    return {"games":len(labels),"holdout_n":len(hold),"tune_window":[TUNE_START,TUNE_END],
            "context_coefficients":list(c),"selected_tune_goalie_window_coeff_shrink":list(best),
            "tune":{"context":score(train,(None,0.,False)),"selected":score(train,best)},
            "holdout":{"context":score(hold,(None,0.,False)),"selected":score(hold,best)},
            "by_phase":groups,"coefficient_policy":"nonnegative coefficient, selected on tune period only",
            "holdout_previously_inspected":True,"odds_used":False,"official_model_promoted":False,
            "limitation":"Team-level goalie aggregates only, not pregame known starters; no independent confirmation."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--features",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();result=fit(read_labels(a.labels),json.loads(Path(a.features).read_text()))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
