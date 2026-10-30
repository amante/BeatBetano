"""ML-only, same-fixture evaluation of sporting challenger vs frozen outcome-only specification.

Baseline parameters (80, .5) are imported from #218, never tuned on holdout.
For each date predict BEFORE incorporating results from that date.
"""
import argparse,csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
from nhl.historical_target_walkforward import prediction
from nhl.pulso_outcome_forecast_218 import PARAMS,VERSION

def outcome_baseline(labels,fixture_ids):
    if len({str(r["game_id"]) for r in labels})!=len(labels):
        raise ValueError("Duplicate historical labels")
    global_counts={"ml":defaultdict(int)}
    team_counts=defaultdict(lambda:{"ml":defaultdict(int)})
    by_day=defaultdict(list)
    for r in labels:
        if r["ml_winner"] not in ("home","away"):raise ValueError("Invalid ML label")
        by_day[r["date"]].append(r)
    result={}
    for day in sorted(by_day):
        games=by_day[day]
        for r in games:
            gid=str(r["game_id"])
            if gid in fixture_ids:
                probs=prediction(global_counts,team_counts,r["home"],r["away"],
                                 "ml",*PARAMS["ml"])
                result[gid]={"date":day,"p_home_ml":probs[0],"y":int(r["ml_winner"]=="home"),
                             "home":r["home"],"away":r["away"]}
        # Freeze all same-date fixtures before observing same-date outcomes.
        for r in games:
            outcome=r["ml_winner"]
            global_counts["ml"][outcome]+=1
            team_counts["home:"+r["home"]]["ml"][outcome]+=1
            team_counts["away:"+r["away"]]["ml"][outcome]+=1
    if set(result)!=fixture_ids:raise ValueError("Baseline missing holdout fixture")
    return result

def score(rows):
    if not rows:raise ValueError("Empty score collection")
    for p,y in rows:
        if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1:
            raise ValueError("Invalid probability")
        if y not in (0,1):raise ValueError("Invalid binary target")
    n=len(rows)
    return {"n":n,"brier":round(sum((p-y)**2 for p,y in rows)/n,7),
            "log_loss":round(-sum(y*math.log(max(p,1e-12))+
                              (1-y)*math.log(max(1-p,1e-12)) for p,y in rows)/n,7)}

def reliability(rows,bins=10):
    buckets=[[] for _ in range(bins)]
    for p,y in rows:
        buckets[min(int(p*bins),bins-1)].append((p,y))
    return [{"bin":i,"n":len(b),"mean_predicted":round(sum(p for p,_ in b)/len(b),6),
             "observed_win_rate":round(sum(y for _,y in b)/len(b),6)}
            for i,b in enumerate(buckets) if b]

def evaluate(challenger,labels):
    if challenger.get("status")!="research_only_challenger_fitted" or challenger.get("promoted") is not False:
        raise ValueError("Unverified challenger")
    preds=challenger["holdout_predictions"]
    if len(preds)!=challenger["holdout_games"] or not preds:raise ValueError("Holdout count mismatch")
    ids=[str(x["game_id"]) for x in preds]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate holdout games")
    fixtures=set(ids)
    lookup=outcome_baseline(labels,fixtures)
    paired=[];years=defaultdict(list)
    for x in preds:
        gid=str(x["game_id"]);ref=lookup[gid]
        if x["date"]!=ref["date"] or x["date"]<challenger["holdout_start"]:
            raise ValueError("Date or holdout mismatch")
        if x["actual_home_ml"]!=ref["y"]:raise ValueError("Actual winner mismatch")
        p=x["p_home_ml"];y=ref["y"];base=ref["p_home_ml"]
        score([(p,y),(base,y)])
        record={"game_id":gid,"date":x["date"],"challenger":p,"baseline":base,"y":y}
        paired.append(record);years[x["date"][:4]].append(record)
    def compare(items):
        a=score([(x["challenger"],x["y"]) for x in items])
        b=score([(x["baseline"],x["y"]) for x in items])
        return {"challenger":a,"outcome_only_baseline":b,
                "delta_brier":round(a["brier"]-b["brier"],7),
                "delta_log_loss":round(a["log_loss"]-b["log_loss"],7)}
    summary=compare(paired)
    return {"status":"completed_research_comparison","market":"ML","holdout_start":challenger["holdout_start"],
            "paired_games":len(paired),"baseline_version":VERSION,"baseline_ml_params":list(PARAMS["ml"]),
            "baseline_calculation":"Prior-date cumulative league and role-specific outcomes, fixed parameters",
            "overall":summary,"by_calendar_year":{year:compare(items) for year,items in sorted(years.items())},
            "reliability":{"challenger":reliability([(r["challenger"],r["y"]) for r in paired]),
             "outcome_only_baseline":reliability([(r["baseline"],r["y"]) for r in paired])},
            "odds_used":False,"official":False,"model_promoted":False,
            "warning":"Single fixed chronological holdout; no walk-forward retraining, bootstrap uncertainty or independent seasonal replication. Negative delta favors challenger."}

def main():
    p=argparse.ArgumentParser()
    for k in ("challenger","labels","out"):p.add_argument("--"+k,required=True)
    a=p.parse_args()
    c=json.loads(Path(a.challenger).read_text())
    with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
    result=evaluate(c,labels)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ("status","paired_games","overall","model_promoted")},indent=2))
if __name__=="__main__":main()
