"""Final historical NHL research closeout: ML, RT, first+3, home+3, away+3.

All model coefficients are tuned exclusively before March 2026. Never promote
research results to an official 14-module forecast. Previously inspected test
set is diagnostic, not a fresh independent validation.
"""
import argparse,json,math,sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START,CATEGORIES
from prior_stats_ml_ablations import prepare
from schedule_context_ablations import context,adjust,scoring
from season_phase_goalie_audit import phase_counts
from rolling_goalie_holdout import fit as rolling_ml_fit

def softmax(xs):
    z=max(xs);a=[math.exp(x-z) for x in xs];return [v/sum(a) for v in a]

def predicted(probs,categories,delta,coefficient):
    if len(probs)!=len(categories):raise ValueError("Target shape mismatch")
    if delta is None or coefficient==0:return probs
    signs=({"home":1,"away":-1,"draw":0,"none":0,"yes":1,"no":-1})
    return softmax([math.log(max(1e-12,p))+coefficient*delta*signs[c] for p,c in zip(probs,categories)])

def scores(rows,target,features,coef,mode="none"):
    categories=CATEGORIES[target]
    total_b=total_ll=0.
    bins=defaultdict(lambda:{"count":0,"probability":0.,"observed":0.})
    for r in rows:
        f=features[r["game_id"]]
        delta=f["skater"] if mode=="skater" else f["goalie"] if mode=="goalie" else None
        p=predicted(r["probs"][target],categories,delta,coef)
        y=categories.index(r["y"][target])
        total_b+=sum((v-int(i==y))**2 for i,v in enumerate(p))/len(p)
        total_ll-=math.log(max(1e-12,p[y]))
        # Calibration on home (or yes) event, kept descriptive on holdout.
        bucket=min(9,int(p[0]*10))
        b=bins[bucket];b["count"]+=1;b["probability"]+=p[0];b["observed"]+=int(y==0)
    n=len(rows)
    if n==0:return {"n":0,"brier":None,"log_loss":None,"calibration":[]}
    return {"n":n,"brier":round(total_b/n,6),"log_loss":round(total_ll/n,6),
            "calibration":[{"bin":i,"n":v["count"],"mean_probability":round(v["probability"]/v["count"],4),
             "observed_rate":round(v["observed"]/v["count"],4)} for i,v in sorted(bins.items())]}

def evaluate(labels,prior,rolling):
    feats=prepare(labels,prior)
    rows=timeline(labels,80,.5)
    tune=[r for r in rows if TUNE_START<=r["date"]<=TUNE_END]
    hold=[r for r in rows if r["date"]>=TEST_START]
    if len(hold)!=554 or len(tune)<200:raise ValueError("Historical partition mismatch")
    phases=phase_counts(labels)
    targets={}
    grid=(-.4,-.2,0.,.2,.4)
    for target in CATEGORIES:
        models={"baseline":("none",0.),"skater":("skater",0.),"goalie":("goalie",0.),"combined":("both",0.)}
        # Distinct ML/RT/+3 target labels. Coefficients chosen on tune only.
        options={}
        for label in ("skater","goalie"):
            best=min(grid,key=lambda k:(scores(tune,target,feats,k,label)["log_loss"],k))
            options[label]={"coefficient":best,"tune":scores(tune,target,feats,best,label),
                            "holdout":scores(hold,target,feats,best,label)}
        # Combined additive logits with independent time-safe scalar features.
        def joint_score(group,coeff):
            g,s=coeff
            transformed=[]
            for r in group:
                x=feats[r["game_id"]]
                # Build combined scalar effect by summing two fixed logits in log space.
                # Multi-class target home/away offsets retain normalization.
                cats=CATEGORIES[target];base=r["probs"][target]
                signs={"home":1,"away":-1,"draw":0,"none":0,"yes":1,"no":-1}
                z=[math.log(max(1e-12,p))+(g*x["goalie"] if x["goalie"] is not None else 0)*signs[c]+
                  (s*x["skater"] if x["skater"] is not None else 0)*signs[c] for p,c in zip(base,cats)]
                transformed.append((softmax(z),cats.index(r["y"][target])))
            n=len(transformed)
            return {"n":n,"brier":round(sum(sum((p-int(i==y))**2 for i,p in enumerate(ps))/len(ps) for ps,y in transformed)/n,6),
                    "log_loss":round(-sum(math.log(max(1e-12,ps[y])) for ps,y in transformed)/n,6)}
        joint_candidates=[(g,s) for g in grid for s in grid]
        best_joint=min(joint_candidates,key=lambda c:(joint_score(tune,c)["log_loss"],c))
        targets[target]={"baseline":{"holdout":scores(hold,target,feats,0.)},
           "skater":options["skater"],"goalie":options["goalie"],
           "combined":{"coefficients":list(best_joint),"tune":joint_score(tune,best_joint),
                      "holdout":joint_score(hold,best_joint)}}
    return {"games":len(labels),"tune_window":[TUNE_START,TUNE_END],"holdout_from":TEST_START,
      "holdout_n":len(hold),"targets":targets,
      "rolling_goalie_ml":rolling_ml_fit(labels,rolling),
      "holdout_phase_counts":{name:sum(phases[r["game_id"]]["both_phase"]==name for r in hold)
            for name in ("opening_1_10","developing_11_25","established_26_plus","mixed")},
      "controls":{"same_day_outcomes_as_inputs":False,"odds_used":False,
          "official_model_promoted":False,"independent_confirmation":False},
      "limitations":["Previously inspected 554-game holdout: diagnostics only.",
        "Team-level prior goalie stats do not identify the future starting goalie.",
        "Historical player scoring does not establish verified future lineups.",
        "RT and +3 are independent experimental output targets; not the full NHL model.",
        "Target-specific tuning on the same tune window is exploratory; external future-season evaluation required."]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--prior",required=True)
    p.add_argument("--rolling",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    report=evaluate(read_labels(a.labels),json.loads(Path(a.prior).read_text()),json.loads(Path(a.rolling).read_text()))
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2))
    print(json.dumps({"games":report["games"],"holdout_n":report["holdout_n"],
       "target_holdout_scores":{t:{m:v["holdout"]["brier"] for m,v in d.items()} for t,d in report["targets"].items()},
       "rolling_goalie_ml":report["rolling_goalie_ml"]["holdout"],
       "holdout_phase_counts":report["holdout_phase_counts"],"controls":report["controls"]},indent=2))
if __name__=="__main__":main()
