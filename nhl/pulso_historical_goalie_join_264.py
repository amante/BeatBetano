"""NHL #264: point-in-time historical game/goalie feature join.

Inputs: outcome labels and independently sourced dated goalie/team observations.
No historical starter or pregame statistic is inferred from postgame results.
"""
import argparse,csv,json
from collections import Counter
from datetime import date
from pathlib import Path
from nhl.pulso_goalie_training_263 import audit,FEATURES

def build(labels, observations):
    by_id={}
    for record in observations:
        gid=str(record.get("game_id",""))
        if not gid or gid in by_id:raise ValueError("Duplicate or missing observed fixture ID")
        by_id[gid]=record
    output=[]; blocked=[];matched=set()
    for label in labels:
        gid=str(label["game_id"])
        rec=by_id.get(gid)
        if rec is None:
            blocked.append({"game_id":gid,"reason":"no_independent_goalie_observation"});continue
        matched.add(gid)
        if (rec.get("date")!=label["date"] or rec.get("home")!=label["home"] or
            rec.get("away")!=label["away"]):
            raise ValueError("Historical fixture identity mismatch")
        if rec.get("source_verified") is not True:
            blocked.append({"game_id":gid,"reason":"unverified_sporting_source"});continue
        try:
            asof=date.fromisoformat(rec["feature_as_of_date"])
            game_day=date.fromisoformat(label["date"])
        except (KeyError,TypeError,ValueError):
            blocked.append({"game_id":gid,"reason":"missing_valid_feature_cutoff"});continue
        if asof>=game_day:
            blocked.append({"game_id":gid,"reason":"postcutoff_or_same_day_features"});continue
        if not all(str(rec.get(key,"")).isdigit() and int(rec[key])>0
                   for key in ("home_goalie_id","away_goalie_id")):
            blocked.append({"game_id":gid,"reason":"missing_independent_starter_ids"});continue
        if any(rec.get(key) is None for key in FEATURES):
            blocked.append({"game_id":gid,"reason":"missing_prior_sporting_features"});continue
        row={key:label[key] for key in ("game_id","date","home","away","ml_winner")}
        row.update({key:rec[key] for key in ("feature_as_of_date","home_goalie_id",
                                            "away_goalie_id")+FEATURES})
        output.append(row)
    if set(by_id)!=matched:raise ValueError("Observation references unknown historical fixture")
    if len({str(x["game_id"]) for x in labels})!=len(labels):
        raise ValueError("Duplicate outcome label")
    status=audit(output) if output else {"status":"blocked_no_verified_joined_rows","training_rows":0}
    return {"kind":"nhl_historical_goalie_join_264","eligible_rows":output,
            "blocked_fixtures":blocked,"label_count":len(labels),
            "eligible_count":len(output),"blocked_count":len(blocked),
            "training_audit":status,"official_predictions":0,
            "odds_used":False,"calibrated":False}

def main():
    p=argparse.ArgumentParser()
    for key in ("labels","observations","out"):p.add_argument("--"+key,required=True)
    a=p.parse_args()
    with Path(a.labels).open(newline="") as handle:labels=list(csv.DictReader(handle))
    with Path(a.observations).open(newline="") as handle:obs=list(csv.DictReader(handle))
    result=build(labels,obs)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ("label_count","eligible_count","blocked_count")}))
if __name__=="__main__":main()
