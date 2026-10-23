"""Segment-by-segment out-of-sample robustness report for NBA Challenger.

No coefficient tuning or acceptance decision is performed on holdout games.
"""
import json,sys
from collections import defaultdict
from math import log,log1p
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import evaluate
from challenger import predict_challenger

def metric(rows):
    if not rows:return {"n":0,"brier_elo":None,"brier_challenger":None,"log_loss_elo":None,"log_loss_challenger":None}
    e=[min(1-1e-12,max(1e-12,x["elo"])) for x in rows]
    c=[min(1-1e-12,max(1e-12,x["challenger"])) for x in rows]
    y=[x["y"] for x in rows]
    return {"n":len(rows),
            "brier_elo":sum((p-t)**2 for p,t in zip(e,y))/len(rows),
            "brier_challenger":sum((p-t)**2 for p,t in zip(c,y))/len(rows),
            "log_loss_elo":-sum(t*log(p)+(1-t)*log1p(-p) for p,t in zip(e,y))/len(rows),
            "log_loss_challenger":-sum(t*log(p)+(1-t)*log1p(-p) for p,t in zip(c,y))/len(rows)}

def report(games):
    games=sorted(games,key=lambda r:(r["tipoff_utc"],str(r["game_id"])))
    if {int(g["season"]) for g in games}!={2024,2025,2026}:raise ValueError("Require exactly three validated seasons")
    for year in (2024,2025,2026):
        if sum(int(g["season"])==year for g in games)!=1230:raise ValueError("Incomplete season")
    elo=list(evaluate(games,season_min=2024,season_max=2026))
    ch=predict_challenger(games)
    output={}
    for yr in (2025,2026):
        rows=[]
        for g,e,c in zip(games,elo,ch):
            if int(g["season"])!=yr:continue
            n=min(c["n_home"],c["n_away"])
            confidence=max(e.p_home,1-e.p_home)
            rows.append({"y":int(float(g["home_points"])>float(g["away_points"])),
                "elo":e.p_home,"challenger":c["p_home"],
                "sample":"0-2" if n<3 else "3-9" if n<10 else "10+",
                "favorite":"50-59%" if confidence<0.60 else "60-69%" if confidence<0.70 else "70-79%" if confidence<0.80 else "80%+",
                "period":"early" if e.prior_games_home<20 or e.prior_games_away<20 else "middle" if e.prior_games_home<60 or e.prior_games_away<60 else "late"})
        segments={}
        for field in ("sample","favorite","period"):
            segments[field]={}
            for key in sorted({x[field] for x in rows}):
                segments[field][key]=metric([x for x in rows if x[field]==key])
        output[str(yr)]={"overall":metric(rows),"segments":segments}
    output["note"]="Exploratory segment inspection only; no holdout-based fitting or production approval."
    return output

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--input",required=True);a.add_argument("--output",required=True)
    args=a.parse_args()
    result=report(json.loads(Path(args.input).read_text()))
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
