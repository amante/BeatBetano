"""Evaluate an externally fitted NBA availability challenger on locked future holdouts.

Input is point-in-time per-game predictions and outcomes. This tool does not fit
coefficients and does not certify model impact from a passing software test.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def moment(x):
    t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() != timezone.utc.utcoffset(t):
        raise ValueError("UTC timestamp required")
    return t


def score(rows):
    n = len(rows)
    return {"n": n,
            "brier": sum((p-y)**2 for p,y in rows)/n,
            "log_loss": -sum(y*math.log(max(1e-12,min(1-1e-12,p))) +
                             (1-y)*math.log(max(1e-12,min(1-1e-12,1-p)))
                             for p,y in rows)/n}


def evaluate(records, min_holdout=100):
    if not isinstance(records,list) or not records:
        raise ValueError("Nonempty records required")
    seen=set()
    by_year=defaultdict(list)
    for r in records:
        gid=str(r["game_id"])
        if gid in seen:raise ValueError("Duplicate game")
        seen.add(gid)
        tip=moment(r["tipoff_utc"])
        freeze=moment(r["prediction_as_of_utc"])
        feature=moment(r["feature_observed_at_utc"])
        trained=moment(r["model_training_cutoff_utc"])
        if not (feature<=freeze<tip and trained<freeze):
            raise ValueError("Temporal leakage or future input")
        if r.get("features_point_in_time_verified") is not True:
            raise ValueError("Unverified availability inputs")
        if not r.get("impact_model_version") or not r.get("training_dataset_hash"):
            raise ValueError("Model provenance absent")
        baseline=r["baseline_p_home"]
        candidate=r["candidate_p_home"]
        if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1
               for p in (baseline,candidate)):
            raise ValueError("Invalid probability")
        y=r["home_won"]
        if type(y) is not int or y not in (0,1):
            raise ValueError("Binary home result required")
        by_year[int(r["season_end_year"])].append((baseline,candidate,y))
    years=sorted(by_year)
    if len(years)<2:
        raise ValueError("At least two separate holdout seasons required")
    reports={}
    all_base=[];all_ch=[]
    for year in years:
        group=by_year[year]
        if len(group)<min_holdout:
            raise ValueError("Insufficient holdout sample for year "+str(year))
        b=[(x,y) for x,_,y in group]
        c=[(x,y) for _,x,y in group]
        all_base.extend(b);all_ch.extend(c)
        sb,sc=score(b),score(c)
        reports[str(year)]={"baseline":sb,"candidate":sc,
                            "brier_gain":sb["brier"]-sc["brier"],
                            "log_loss_gain":sb["log_loss"]-sc["log_loss"]}
    pooled_b,pooled_c=score(all_base),score(all_ch)
    improved=all(x["brier_gain"]>0 and x["log_loss_gain"]>0 for x in reports.values())
    return {"schema_version":1,"holdout_seasons":years,
            "by_season":reports,"pooled":{"baseline":pooled_b,"candidate":pooled_c},
            "improved_all_holdouts":improved,
            "independent_validation_passed":False,
            "automatic_promotion_allowed":False,
            "note":"Descriptive holdout test only. Independent audit, data coverage, calibration, registered protocol and ablations required before approval."}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--min-holdout",type=int,default=100)
    args=ap.parse_args()
    report=evaluate(json.loads(Path(args.input).read_text()),args.min_holdout)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2))
    print(json.dumps({"years":report["holdout_seasons"],
                      "improved_all_holdouts":report["improved_all_holdouts"],
                      "independent_validation_passed":False}))

if __name__=="__main__":
    main()
