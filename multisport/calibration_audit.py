"""Point-in-time, out-of-sample calibration audit for NBA/NHL binary markets.

This measures historical forecasts; it does not train, recalibrate or approve
final probabilities. NHL regulation, ML incl OT and +3 are distinct markets.
"""
import argparse,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

MARKETS={"nba":{"moneyline"},"nhl":{"moneyline","regulation_home","three_goal_lead_home","first_to_plus_three_home"}}

def moment(x):
    d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timezone.utc.utcoffset(d):
        raise ValueError("Expected UTC timestamp")
    return d

def score(pairs):
    n=len(pairs)
    if not n:raise ValueError("Empty scored sample")
    bs=sum((p-y)**2 for p,y in pairs)/n
    ll=-sum(y*math.log(max(1e-12,min(1-1e-12,p)))+
       (1-y)*math.log(max(1e-12,min(1-1e-12,1-p))) for p,y in pairs)/n
    bins=[]
    for i in range(10):
        q=[(p,y) for p,y in pairs if min(int(p*10),9)==i]
        bins.append({"lower":i/10,"upper":(i+1)/10,"n":len(q),
          "forecast_mean":sum(p for p,y in q)/len(q) if q else None,
          "outcome_rate":sum(y for p,y in q)/len(q) if q else None})
    return {"n":n,"brier":bs,"log_loss":ll,"reliability_bins":bins}

def audit(records,sport,market="moneyline",min_games_per_season=100):
    if sport not in MARKETS or market not in MARKETS[sport]:raise ValueError("Unsupported sport/market")
    if not isinstance(records,list) or not records:raise ValueError("Nonempty records required")
    byseason=defaultdict(lambda:defaultdict(list));seen=set();versions=set()
    for x in records:
        gid=str(x["game_id"])
        if gid in seen:raise ValueError("Duplicate event")
        seen.add(gid)
        if x.get("sport")!=sport or x.get("market")!=market:raise ValueError("Mixed sports/markets")
        freeze=moment(x["prediction_as_of_utc"]);tip=moment(x["tipoff_utc"])
        feature=moment(x["latest_feature_observed_at_utc"])
        train=moment(x["training_cutoff_utc"])
        if not (feature<=freeze<tip and train<freeze):raise ValueError("Temporal leakage")
        if x.get("point_in_time_sources_verified") is not True:raise ValueError("Unverified historical data")
        if x.get("market_odds_used") is not False:raise ValueError("Market odds are not allowed")
        version=x.get("model_version")
        if not version or not x.get("training_dataset_hash"):raise ValueError("Missing model lineage")
        versions.add(version)
        y=x["outcome"]
        if type(y) is not int or y not in (0,1):raise ValueError("Binary market outcome required")
        for name in ("baseline","challenger"):
            p=x.get(name+"_p")
            if p is None:continue
            if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1:
                raise ValueError("Invalid probability")
            byseason[int(x["season_end_year"])][name].append((p,y))
        if x.get("baseline_p") is None:raise ValueError("Every match needs a baseline")
    if len(versions)!=1:raise ValueError("Mixed model versions")
    years=sorted(byseason)
    metrics={}
    for year in years:
        b=byseason[year]["baseline"]
        if len(b)<min_games_per_season:raise ValueError("Insufficient annual holdout")
        metrics[str(year)]={"baseline":score(b)}
        c=byseason[year]["challenger"]
        if len(c)==len(b):
            metrics[str(year)]["challenger"]=score(c)
            metrics[str(year)]["challenger_brier_gain"]=metrics[str(year)]["baseline"]["brier"]-metrics[str(year)]["challenger"]["brier"]
            metrics[str(year)]["challenger_log_loss_gain"]=metrics[str(year)]["baseline"]["log_loss"]-metrics[str(year)]["challenger"]["log_loss"]
    return {"schema_version":1,"sport":sport,"market":market,"model_version":next(iter(versions)),
      "holdout_years":years,"by_season":metrics,
      "at_least_two_holdout_seasons":len(years)>=2,
      "independent_validation_passed":False,"automatic_promotion_allowed":False,
      "note":"Descriptive scoring only. Independent source/lineage audit, chronological training review, baseline ablation and reliability protocol required."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--sport",required=True)
    p.add_argument("--market",default="moneyline");p.add_argument("--min-games",type=int,default=100)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    out=audit(json.loads(Path(a.input).read_text()),a.sport,a.market,a.min_games)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2))
    print(json.dumps({"years":out["holdout_years"],"independent_validation_passed":False}))
if __name__=="__main__":main()
