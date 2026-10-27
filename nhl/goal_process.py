"""Exploratory NHL 60-minute goal-process baseline.

Unfitted Poisson model: transparent, bounded inputs, no bookmakers.
Not official/challenger probabilities and not calibrated or bet-authorized.
"""
import argparse,json,math
from factor_engine import process
from pathlib import Path

def poisson(mean,kmax=30):
    p=[math.exp(-mean)]
    for n in range(1,kmax+1):p.append(p[-1]*mean/n)
    p[-1]+=max(0.,1-sum(p))
    return p

def goal_rates(home,away):
    h=home["crs_evidence"];a=away["crs_evidence"]
    fields=("games_played","goals_for_per_game","goals_against_per_game")
    for x in (h,a):
        if any(x.get(f) is None for f in fields):raise ValueError("Missing actual goals and game counts")
        if x["games_played"]<=0:raise ValueError("No played games")
        if any(not isinstance(x[f],(int,float)) or not math.isfinite(x[f]) or x[f]<0 for f in fields):
            raise ValueError("Invalid NHL scoring data")
    # Fixed illustrative prior, not trained: shrink both offense and defense rates.
    # Avoid misleading early-season extremes.
    def shrunk(x,key):
        gp=x["games_played"]
        return (gp*x[key]+10*3.0)/(gp+10)
    lh=0.5*(shrunk(h,"goals_for_per_game")+shrunk(a,"goals_against_per_game"))
    la=0.5*(shrunk(a,"goals_for_per_game")+shrunk(h,"goals_against_per_game"))
    return lh,la

def calculate(lh,la):
    if not (0<lh<10 and 0<la<10):raise ValueError("Invalid rates")
    hp=poisson(lh);ap=poisson(la)
    wh=sum(p*q for i,p in enumerate(hp) for j,q in enumerate(ap) if i>j)
    wa=sum(p*q for i,p in enumerate(hp) for j,q in enumerate(ap) if i<j)
    draw=max(0,1-wh-wa)
    # Goal-event process: both 3-goal leads can happen, and first-to-3 is exclusive.
    total=lh+la;prob=lh/total
    # (score difference, has_home_3, has_away_3, first_hit)
    states={(0,False,False,0):1.0}
    outcomes={"home3":0.,"away3":0.,"home_first":0.,"away_first":0.}
    weights=poisson(total,45)
    for n,weight in enumerate(weights):
        if n: # Generate exactly n score events from n-1
            nxt={}
            for (diff,hh,aa,first),v in states.items():
                for d,p in ((1,prob),(-1,1-prob)):
                    newdiff=diff+d
                    nh=hh or newdiff>=3;na=aa or newdiff<=-3
                    first2=first if first else (1 if not hh and nh else 2 if not aa and na else 0)
                    key=(newdiff,nh,na,first2)
                    nxt[key]=nxt.get(key,0)+v*p
            states=nxt
        outcomes["home3"]+=weight*sum(v for (d,hh,aa,f),v in states.items() if hh)
        outcomes["away3"]+=weight*sum(v for (d,hh,aa,f),v in states.items() if aa)
        outcomes["home_first"]+=weight*sum(v for (d,hh,aa,f),v in states.items() if f==1)
        outcomes["away_first"]+=weight*sum(v for (d,hh,aa,f),v in states.items() if f==2)
    return {"lambda_home":round(lh,4),"lambda_away":round(la,4),
       "regulation":{"home":round(wh,5),"draw":round(draw,5),"away":round(wa,5)},
       "illustrative_ml":{"home":round(wh+draw/2,5),"away":round(wa+draw/2,5)},
       "three_goal_lead":{"home":round(outcomes["home3"],5),"away":round(outcomes["away3"],5)},
       "first_to_three_goal_lead":{"home":round(outcomes["home_first"],5),"away":round(outcomes["away_first"],5)},
       "model":"unfitted_independent_poisson_shrunken_goals",
       "calibrated":False,"official":False,"challenger":False,"bet_authorized":False}

def run(evidence):
    outputs=[]
    for game in evidence["games"]:
        factors=process(game)
        lh,la=factors["home_goals_rate"],factors["away_goals_rate"]
        outputs.append({"event_id":game["event_id"],"home":game["home_team"],
                        "away":game["away_team"],"factor_audit":factors["factor_audit"],**calculate(lh,la)})
    return {"as_of_utc":evidence["as_of_utc"],"games":outputs,"odds_used":False,
            "calibrated":False,"model":"exploratory_only"}

def markdown(result):
    lines=["## NHL — exploratory goal-process projections (NOT calibrated)","",
    "Not official or challenger. Five-game shrinkage and small untrained shot proxy; independent Poisson with 50/50 overtime. Goalie, PP/PK, actual lines and rivalry are documented but NOT applied without verified inputs and fitted coefficients. Not betting-authorized.","",
    "| Game | ML A/H% | RT A/X/H% | +3 lead A/H% | First +3 A/H% |",
    "|---|---|---|---|---|"]
    fmt=lambda x:f"{100*x:.1f}"
    for r in result["games"]:
        ml=r["illustrative_ml"];rt=r["regulation"];lead=r["three_goal_lead"];first=r["first_to_three_goal_lead"]
        lines.append(f'| {r["away"]} @ {r["home"]} | {fmt(ml["away"])} / {fmt(ml["home"])} | {fmt(rt["away"])} / {fmt(rt["draw"])} / {fmt(rt["home"])} | {fmt(lead["away"])} / {fmt(lead["home"])} | {fmt(first["away"])} / {fmt(first["home"])} |')
    return "\n".join(lines)+"\n"
def main():
    p=argparse.ArgumentParser()
    for arg in ("input","output","summary"):p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    result=run(json.loads(Path(a.input).read_text()))
    for name,body in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result))):
        dest=Path(name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(body)
    print(json.dumps({"games":len(result["games"]),"calibrated":False}))
if __name__=="__main__":main()
