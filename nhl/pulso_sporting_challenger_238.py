"""NHL sporting challenger v0: chronological research logistic model, no odds.

Uses prior-date TEAM save percentage and skater scoring only. Does not model
confirmed goalies, availability, PP/PK, or official PULSO probabilities.
"""
import argparse,hashlib,json,math
from pathlib import Path

def prepare(rows,minimum_games=5):
    if not isinstance(rows,list):raise ValueError("Historical rows must be a list")
    seen=set();prepared=[];reject={}
    for row in rows:
        gid=str(row.get("game_id",""))
        if not gid or gid in seen:raise ValueError("Missing/duplicate game ID")
        seen.add(gid)
        f=row.get("features",{})
        try:
            h=f["home"];a=f["away"]
            if any(t["past_games"]<minimum_games for t in (h,a)):raise ValueError("thin_prior_sample")
            vals=[h["prior_goalie_save_pct"],a["prior_goalie_save_pct"],
                  h["prior_skater_goals_per_observed_game"],a["prior_skater_goals_per_observed_game"]]
            if any(v is None or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):
                raise ValueError("missing_or_invalid_core")
            if any(not 0<=v<=1 for v in vals[:2]) or any(v<0 for v in vals[2:]):
                raise ValueError("out_of_range")
            outcome=row["target"]["ml_winner"]
            if outcome not in ("home","away"):raise ValueError("invalid_target")
            if not row.get("date"):raise ValueError("missing_date")
            prepared.append({"game_id":gid,"date":row["date"],
                "x":[vals[0]-vals[1],vals[2]-vals[3]],"y":int(outcome=="home")})
        except (KeyError,TypeError) as exc:
            raise ValueError("Malformed historic research row") from exc
        except ValueError as exc:
            reason=str(exc);reject[reason]=reject.get(reason,0)+1
    return sorted(prepared,key=lambda x:(x["date"],x["game_id"])),reject

def split(rows,min_train=200,min_test=100):
    dates=sorted({r["date"] for r in rows})
    if len(dates)<5:raise ValueError("Insufficient chronological dates")
    start=dates[int(len(dates)*.8)]
    train=[r for r in rows if r["date"]<start]
    test=[r for r in rows if r["date"]>=start]
    if len(train)<min_train or len(test)<min_test:
        raise ValueError("Insufficient chronological train/test samples")
    return train,test,start

def sigmoid(z):
    if z>=0:return 1/(1+math.exp(-z))
    e=math.exp(z);return e/(1+e)

def train(rows,epochs=1000,rate=.05,l2=.01):
    if len({r["y"] for r in rows})!=2:raise ValueError("Both ML classes required")
    n=len(rows);means=[sum(r["x"][j] for r in rows)/n for j in (0,1)]
    scales=[max(math.sqrt(sum((r["x"][j]-means[j])**2 for r in rows)/n),1e-8) for j in (0,1)]
    weights=[0.,0.]
    p=sum(r["y"] for r in rows)/n
    bias=math.log(p/(1-p))
    for _ in range(epochs):
        gw=[0.,0.];gb=0.
        for row in rows:
            z=[(row["x"][j]-means[j])/scales[j] for j in (0,1)]
            err=sigmoid(bias+sum(weights[j]*z[j] for j in (0,1)))-row["y"]
            gb+=err
            for j in (0,1):gw[j]+=err*z[j]
        bias-=rate*gb/n
        for j in (0,1):weights[j]-=rate*(gw[j]/n+l2*weights[j])
    return {"means":means,"scales":scales,"weights":weights,"bias":bias,
            "features":["team_prior_goalie_sv_diff","team_prior_skater_goals_diff"],
            "training_games":n,"regularization_l2":l2,"epochs":epochs}

def predict(model,row):
    z=sum(model["weights"][j]*(row["x"][j]-model["means"][j])/model["scales"][j] for j in (0,1))
    return sigmoid(model["bias"]+z)

def run(dataset,audit,min_train=200,min_test=100):
    if audit.get("status")!="historical_sporting_coverage_research_only":
        raise ValueError("Verified #237 coverage report required")
    if audit.get("games")!=len(dataset):raise ValueError("Coverage report and dataset disagree")
    rows,rejected=prepare(dataset,audit["minimum_prior_games"])
    if audit["eligible_games"]!=len(rows):raise ValueError("Eligible row count disagrees with audit")
    training,holdout,cutoff=split(rows,min_train,min_test)
    model=train(training)
    forecasts=[{"game_id":r["game_id"],"date":r["date"],"p_home_ml":round(predict(model,r),8),
                "actual_home_ml":r["y"]} for r in holdout]
    return {"status":"research_only_challenger_fitted","official":False,"promoted":False,
            "market":"ML only","odds_used":False,"training_start":training[0]["date"],
            "training_end":training[-1]["date"],"holdout_start":cutoff,
            "train_games":len(training),"holdout_games":len(holdout),
            "rejected":rejected,"model":model,"holdout_predictions":forecasts,
            "limitations":"Fixed chronological holdout, not yet walk-forward; team aggregates are not confirmed starting goalies. Do not promote before external validation and baseline comparison."}

def main():
    p=argparse.ArgumentParser()
    for name in ("dataset","coverage","out"):p.add_argument("--"+name,required=True)
    a=p.parse_args()
    data=json.loads(Path(a.dataset).read_text())
    coverage=json.loads(Path(a.coverage).read_text())
    result=run(data,coverage)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ("status","train_games","holdout_games","holdout_start","promoted")},indent=2))
if __name__=="__main__":main()
