"""Experimental, explicitly post-hoc Challenger guardrails.

Rules were motivated by 2024-25/2025-26 segment inspection, so those seasons
must NOT be used as independent proof of any improvement from these rules.
"""
import json,sys
from pathlib import Path
from math import log,log1p
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import evaluate
from challenger import predict_challenger

def guardrail(elo_probability,challenger_probability,n_home,n_away):
    if not all(0<=p<=1 for p in (elo_probability,challenger_probability)):
        raise ValueError("Invalid probabilities")
    if min(n_home,n_away)<3:
        return elo_probability,"insufficient_recent_sample"
    if max(elo_probability,1-elo_probability)>=0.80:
        return elo_probability,"strong_favorite"
    return challenger_probability,"challenger"

def measure(items,key):
    if not items:raise ValueError("Empty benchmark")
    ps=[max(1e-12,min(1-1e-12,r[key])) for r in items]
    ys=[r["outcome"] for r in items]
    return {"n":len(items),"brier":sum((p-y)**2 for p,y in zip(ps,ys))/len(items),
        "log_loss":-sum(y*log(p)+(1-y)*log1p(-p) for p,y in zip(ps,ys))/len(items)}

def compare(games):
    games=sorted(games,key=lambda r:(r["tipoff_utc"],str(r["game_id"])))
    if {int(g["season"]) for g in games}!={2024,2025,2026}:
        raise ValueError("Require exactly three seasons")
    for yr in (2024,2025,2026):
        if sum(int(g["season"])==yr for g in games)!=1230:
            raise ValueError("Incomplete season")
    baselines=list(evaluate(games,season_min=2024,season_max=2026))
    candidates=predict_challenger(games)
    out={}
    for yr in (2025,2026):
        rows=[];counts={}
        for g,e,c in zip(games,baselines,candidates):
            if e.season!=yr:continue
            p,reason=guardrail(e.p_home,c["p_home"],c["n_home"],c["n_away"])
            counts[reason]=counts.get(reason,0)+1
            rows.append({"elo":e.p_home,"challenger":c["p_home"],"guarded":p,
                "outcome":int(float(g["home_points"])>float(g["away_points"]))})
        out[str(yr)]={"elo":measure(rows,"elo"),"challenger":measure(rows,"challenger"),
            "guarded":measure(rows,"guarded"),"route_counts":counts}
    out["production_approved"]=False
    out["holdout_independence"]="NOT independent: guardrails chosen after inspecting these seasons"
    out["validation_required"]="Evaluate on a future untouched season or frozen forward test"
    return out

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--input",required=True);a.add_argument("--output",required=True)
    args=a.parse_args()
    result=compare(json.loads(Path(args.input).read_text()))
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
