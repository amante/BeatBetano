"""Leakage-free outcome-target benchmark on official NHL postgame labels.

Produces provisional empirical baseline and shrinkage challenger only;
NOT the 14-module NHL official/challenger model. No odds, postgame covariates,
goalie data, or final-game statistics from the predicted fixture.
"""
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path

CATEGORIES={"ml":("home","away"),"rt":("home","draw","away"),
            "first3":("home","away","none"),"home3":("yes","no"),
            "away3":("yes","no")}
TUNE_START="2025-10-01"
TUNE_END="2026-02-28"
TEST_START="2026-03-01"

def read_labels(path):
    with Path(path).open(newline="") as f: rows=list(csv.DictReader(f))
    if len(rows)!=2811:raise ValueError(f"Expected 2811 records, got {len(rows)}")
    if len({r["game_id"] for r in rows})!=len(rows):raise ValueError("Duplicate games")
    required=("date","home","away","ml_winner","rt_result",
              "home_reached_plus3","away_reached_plus3")
    for r in rows:
        if any(k not in r or not r[k] for k in required):raise ValueError("Incomplete target labels")
        if r["ml_winner"] not in ("home","away") or r["rt_result"] not in ("home","draw","away"):raise ValueError("Invalid winner")
        # CSV DictWriter serializes Python None as an empty field.
        # For first-to-+3, empty means neither side reached a three-goal lead.
        if "first_to_plus3" not in r or r["first_to_plus3"] not in ("home","away","None",""):
            raise ValueError("Invalid first-to-+3")
        if any(r[k] not in ("True","False") for k in ("home_reached_plus3","away_reached_plus3")):raise ValueError("Invalid 3GLP boolean")
        if r["first_to_plus3"]=="home" and r["home_reached_plus3"]!="True":raise ValueError("First+3 home impossible")
        if r["first_to_plus3"]=="away" and r["away_reached_plus3"]!="True":raise ValueError("First+3 away impossible")
    return sorted(rows,key=lambda r:(r["date"],r["game_id"]))

def outcomes(r):
    return {"ml":r["ml_winner"],"rt":r["rt_result"],
            "first3":"none" if r["first_to_plus3"] in ("None","") else r["first_to_plus3"],
            "home3":"yes" if r["home_reached_plus3"]=="True" else "no",
            "away3":"yes" if r["away_reached_plus3"]=="True" else "no"}

def season(r):
    d=r["date"];return int(d[:4]) if int(d[5:7])>=7 else int(d[:4])-1

def normalize(values):
    total=sum(values)
    if total<=0:raise ValueError("Empty probability vector")
    return [max(1e-12,x/total) for x in values]

def prediction(global_counts,team_counts,home,away,target,shrink,team_weight):
    cats=CATEGORIES[target]
    glob=global_counts[target]
    prior=normalize([glob[c]+1 for c in cats])
    home_c=team_counts["home:"+home][target];away_c=team_counts["away:"+away][target]
    # Team role-specific, date-past event counts; no target-game outcome.
    role_counts=[(home_c[c]+away_c[c]) for c in cats]
    total=sum(role_counts)
    if total==0:return prior
    return normalize([team_weight*role_counts[i]+shrink*prior[i] for i in range(len(cats))])

def timeline(rows,shrink,team_weight):
    global_counts={t:defaultdict(int) for t in CATEGORIES}
    team_counts=defaultdict(lambda:{t:defaultdict(int) for t in CATEGORIES})
    result=[]
    by_date=defaultdict(list)
    for r in rows:by_date[r["date"]].append(r)
    for day in sorted(by_date):
        # ALL games on the same date use only earlier dates.
        for r in by_date[day]:
            y=outcomes(r)
            preds={}
            for target in CATEGORIES:
                preds[target]=prediction(global_counts,team_counts,r["home"],r["away"],target,shrink,team_weight)
            result.append({"date":day,"game_id":r["game_id"],"y":y,"probs":preds})
        for r in by_date[day]:
            y=outcomes(r)
            for t,v in y.items():
                global_counts[t][v]+=1
                team_counts["home:"+r["home"]][t][v]+=1
                team_counts["away:"+r["away"]][t][v]+=1
    return result

def metrics(entries):
    if not entries:raise ValueError("Empty holdout")
    out={}
    for target,cats in CATEGORIES.items():
        n=len(entries);brier=0.;loss=0.
        for row in entries:
            probs=row["probs"][target]
            if len(probs)!=len(cats):raise ValueError("Probability shape")
            idx=cats.index(row["y"][target])
            brier+=sum((p-(i==idx))**2 for i,p in enumerate(probs))/len(cats)
            loss-=math.log(max(1e-12,probs[idx]))
        out[target]={"n":n,"brier":round(brier/n,6),"log_loss":round(loss/n,6)}
    return out

def evaluate(rows):
    # Tunable parameters chosen ONLY from tune period, never future holdout.
    candidates=[(shrink,weight) for shrink in (8,20,40,80) for weight in (0.,0.5,1.)]
    tune=lambda seq:[p for p in seq if TUNE_START<=p["date"]<=TUNE_END]
    test=lambda seq:[p for p in seq if p["date"]>=TEST_START]
    trials=[]
    for sh,w in candidates:
        seq=timeline(rows,sh,w);part=tune(seq)
        if len(part)<200:raise ValueError("Insufficient tuning events")
        score=metrics(part)
        trials.append((score["ml"]["log_loss"],sh,w))
    _,selected_sh,selected_w=min(trials)
    selected=timeline(rows,selected_sh,selected_w)
    reference=timeline(rows,20,0.)
    hold=test(selected);reference_hold=test(reference)
    if len(hold)<100:raise ValueError("Insufficient untouched holdout events")
    # Note: first 2026-27 games still use cumulative previous season with the
    # date-past process; model must be further validated for roster drift.
    return {"source_games":len(rows),"tune_window":[TUNE_START,TUNE_END],
       "test_from":TEST_START,"test_n":len(hold),
       "candidate_parameters":{"shrink":selected_sh,"team_weight":selected_w},
       "candidate_test":metrics(hold),"reference_test":metrics(reference_hold),
       "selection_target":"ML tune log_loss only; all targets evaluated on untouched test",
       "baseline_definition":"Cumulative league outcome frequencies from prior dates",
       "candidate_definition":"Past team outcome counts with prior shrinkage",
       "point_in_time":"Only previous-date historical label aggregates (no past-as-of feed proof)",
       "odds_used":False,"not_full_14_module_model":True,
       "automatic_promotion":False,"independent_validation_passed":False,
       "claim":"research benchmark not an official NHL 2026-27/2026-27.1 forecast"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=evaluate(read_labels(a.labels))
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
