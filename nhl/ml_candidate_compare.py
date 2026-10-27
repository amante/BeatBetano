"""Evaluate frozen historical ML candidate and compare to current exploratory goals-only proxy.

Training and test outcomes remain separated. Does not claim PR132 shot-factor
validation, because the weekly results feed has no historical shot features.
"""
import argparse,json,math
from pathlib import Path
from collections import defaultdict
from walkforward_calibration import predict

FROZEN={"prior_goals":2.8,"home_log_adjustment":0.16,"shrink_games":5,
        "source_run":"40600857882","source_train_through":"2025-06-30",
        "source_holdout_from":"2025-10-01"}

def historical_form(prior,team):
    games=[x for x in prior if team in (x["home"],x["away"])]
    gf=sum(x["hg"] if x["home"]==team else x["ag"] for x in games)
    ga=sum(x["ag"] if x["home"]==team else x["hg"] for x in games)
    return gf,ga,len(games)

def comparison(rows,holdout_from="2025-10-01"):
    from walkforward_calibration import ml
    byday=defaultdict(list)
    for x in rows:byday[x["date"]].append(x)
    prior=[];out=[]
    for day in sorted(byday):
        if day>=holdout_from:
            for game in byday[day]:
                p=predict(prior,game,FROZEN["prior_goals"],FROZEN["home_log_adjustment"],FROZEN["shrink_games"])
                # PR132-inspired goal-only approximation: center 3, prior 5,
                # zero home adjustment; shot volume cannot be reconstructed
                # from this results-only historical data.
                h=historical_form(prior,game["home"])
                a=historical_form(prior,game["away"])
                def rate(form,field):
                    return (form[field]+15)/(form[2]+5)
                lh=(rate(h,0)+rate(a,1))/2
                la=(rate(a,0)+rate(h,1))/2
                proxy=ml(lh,la)
                out.append({"date":day,"event_id":game["id"],"actual_home_win":int(game["hg"]>game["ag"]),
                            "candidate_ml_home":p,"goal_only_proxy_ml_home":proxy})
        prior.extend(byday[day])
    if not out:raise ValueError("No holdout games")
    def metrics(items,key):
        n=len(items)
        return {"n":n,"brier":round(sum((x[key]-x["actual_home_win"])**2 for x in items)/n,6),
                "log_loss":round(-sum(x["actual_home_win"]*math.log(max(1e-12,x[key]))+
                   (1-x["actual_home_win"])*math.log(max(1e-12,1-x[key])) for x in items)/n,6),
                "mean_predicted_home":round(sum(x[key] for x in items)/n,4),
                "actual_home_win_rate":round(sum(x["actual_home_win"] for x in items)/n,4)}
    segments={}
    for season in ("2025","2026"):
        sub=[x for x in out if x["date"][:4]==season]
        if sub:segments[season]={"candidate":metrics(sub,"candidate_ml_home"),
             "goal_only_proxy":metrics(sub,"goal_only_proxy_ml_home")}
    for lower,upper in ((0,.45),(.45,.5),(.5,.55),(.55,1.001)):
        sub=[x for x in out if lower<=x["candidate_ml_home"]<upper]
        if sub:segments[f"prob_{lower:.2f}_{upper:.2f}"]={"candidate":metrics(sub,"candidate_ml_home")}
    return {"frozen_parameters":FROZEN,"holdout_from":holdout_from,
        "candidate":metrics(out,"candidate_ml_home"),
        "goal_only_proxy":metrics(out,"goal_only_proxy_ml_home"),
        "segments":segments,"predictions":out,
        "candidate_is_new_model_for_live_pregame":False,
        "full_pr132_model_validated":False,
        "promotion_authorized":False,
        "warning":"Results-only history lacks shot volume, current roster, goalie, PP/PK; goal-only comparator is NOT full PR132."}

def markdown(r):
    lines=["## NHL ML candidate — strictly chronological comparison","",
      "Frozen historical parameters from run "+r["frozen_parameters"]["source_run"]+".",
      "**No model promotion:** historical comparison excludes shot factors, goalie, PP/PK and roster effects.","",
      "| Model | N | Brier ↓ | Log loss ↓ | Mean P(home) | Observed home win |",
      "|---|---:|---:|---:|---:|---:|"]
    for key in ("candidate","goal_only_proxy"):
        x=r[key]
        lines.append(f'| {key} | {x["n"]} | {x["brier"]} | {x["log_loss"]} | {x["mean_predicted_home"]} | {x["actual_home_win_rate"]} |')
    lines+=["","### Calibration segments","",
      "| Segment | N | Brier | Mean predicted | Actual |","|---|---:|---:|---:|---:|"]
    for name,part in r["segments"].items():
        x=part["candidate"]
        lines.append(f'| {name} | {x["n"]} | {x["brier"]} | {x["mean_predicted_home"]} | {x["actual_home_win_rate"]} |')
    lines+=["","**Status: research candidate only; neither official nor challenger is promoted.**"]
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    for arg in ("history","output","summary"):p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    rows=json.loads(Path(a.history).read_text())
    report=comparison(rows)
    for path,contents in ((a.output,json.dumps(report,indent=2)),(a.summary,markdown(report))):
        destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(contents)
    print(json.dumps({key:report[key] for key in ("candidate","goal_only_proxy","promotion_authorized")}))
if __name__=="__main__":main()
