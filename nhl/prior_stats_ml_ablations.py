"""Sealed NHL ML holdout ablation of prior-date goalie/skater team aggregates.

No starting goalie inference, same-day leakage, bookmaker odds or auto-promotion.
Fit additive coefficients on tune dates only; report all holdout comparisons.
"""
import argparse,json,hashlib,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START

FEATURES=("goalie","skater")
def prepare(labels,observations):
    if len(observations)!=len(labels):raise ValueError("Feature/label coverage mismatch")
    lookup={str(r["game_id"]):r for r in observations}
    if len(lookup)!=len(observations):raise ValueError("Duplicate evidence game ID")
    result={}
    for r in labels:
        gid=str(r["game_id"]);o=lookup.get(gid)
        if not o or o["date"]!=r["date"] or o.get("source_class")!="earlier_dates_postgame_boxscores_only":
            raise ValueError("Unverified/misaligned prior-date evidence: "+gid)
        if any(o[s].get("pregame_starter_confirmed") is not False or o[s].get("pregame_roster_confirmed") is not False for s in ("home","away")):
            raise ValueError("Incorrect pregame certification")
        h=o["home"];a=o["away"]
        def diff(k):
            x=h.get(k);y=a.get(k)
            return max(-4.,min(4.,float(x)-float(y))) if isinstance(x,(int,float)) and isinstance(y,(int,float)) and math.isfinite(x) and math.isfinite(y) else None
        result[gid]={"goalie":diff("prior_goalie_save_pct"),"skater":diff("prior_skater_goals_per_observed_game")}
    return result

def probability(base,feat,coeff):
    z=math.log(base/(1-base))
    for k in FEATURES:
        if feat[k] is not None:z+=coeff[k]*feat[k]
    return 1/(1+math.exp(-max(-30,min(30,z))))

def measure(rows,evidence,coeff):
    if not rows:raise ValueError("Empty evaluation group")
    b=ll=0.
    for r in rows:
        p=probability(r["probs"]["ml"][0],evidence[r["game_id"]],coeff)
        y=int(r["y"]["ml"]=="home")
        b+=(p-y)**2
        ll-=y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p))
    return {"n":len(rows),"brier":round(b/len(rows),6),"log_loss":round(ll/len(rows),6)}

def compare(labels,observations):
    evidence=prepare(labels,observations)
    rows=timeline(labels,80,.5)
    tune=[r for r in rows if TUNE_START<=r["date"]<=TUNE_END]
    hold=[r for r in rows if r["date"]>=TEST_START]
    if len(tune)<200 or len(hold)<100:raise ValueError("Insufficient tune/test periods")
    configs={
      "baseline":[(0.,0.)],
      "goalie_only":[(g,0.) for g in (-4.,-2.,0.,2.,4.)],
      "skater_only":[(0.,s) for s in (-.2,-.1,0.,.1,.2)],
      "goalie_and_skater":[(g,s) for g in (-4.,-2.,0.,2.,4.) for s in (-.2,-.1,0.,.1,.2)]
    }
    result={}
    for name,grid in configs.items():
        candidates=[({"goalie":g,"skater":s},g,s) for g,s in grid]
        winner=min(candidates,key=lambda x:(measure(tune,evidence,x[0])["log_loss"],x[1],x[2]))
        c=winner[0]
        result[name]={"coefficients":c,"tune":measure(tune,evidence,c),
                      "holdout":measure(hold,evidence,c)}
    return {"source_games":len(labels),"holdout_n":len(hold),"tune_window":[TUNE_START,TUNE_END],
      "test_from":TEST_START,"ablations":result,
      "feature_coverage_in_holdout":{k:sum(evidence[r["game_id"]][k] is not None for r in hold) for k in FEATURES},
      "odds_used":False,"same_game_confirmed_starter":False,"official_model_promoted":False,
      "limitation":"Research ML-only team aggregates from earlier dates. No confirmed prospective lineups, goalie starters, PP/PK, or 14-module official challenger."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--features",required=True);p.add_argument("--output",required=True)
    args=p.parse_args();report=compare(read_labels(args.labels),json.loads(Path(args.features).read_text()))
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
