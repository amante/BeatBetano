"""NBA Challenger v0.1: pre-tipoff rolling point differential + rest overlay.

Preserves Elo as prior. Fixed coefficients are *hypotheses*, not fitted and
not yet accepted for production. Same-tipoff fixtures use frozen prior state.
"""
from collections import defaultdict,deque
from datetime import datetime,timezone
from math import exp,log
from model import evaluate,probability,dual_eligible,score

def predict_challenger(rows,window=10):
    rows=list(rows)
    base=list(evaluate(rows,season_min=min(int(r["season"]) for r in rows),
                       season_max=max(int(r["season"]) for r in rows)))
    history=defaultdict(lambda:deque(maxlen=window))
    last_day={}
    output=[]
    previous_season=None
    for row,pred in zip(rows,base):
        season=int(row["season"])
        if previous_season is not None and season!=previous_season:
            history=defaultdict(lambda:deque(maxlen=window))
            last_day={}
        previous_season=season
        day=datetime.fromisoformat(row["tipoff_utc"].replace("Z","+00:00")).date()
        h,a=row["home_team"],row["away_team"]
        # Both features are available strictly before this game's outcome.
        mh=sum(history[h])/len(history[h]) if history[h] else 0.0
        ma=sum(history[a])/len(history[a]) if history[a] else 0.0
        margin_effect=max(-12.0,min(12.0,mh-ma))
        def rest(team):
            if team not in last_day:return 0
            return min(4,max(0,(day-last_day[team]).days-1))
        rest_effect=max(-2,min(2,rest(h)-rest(a)))
        prior=max(1e-8,min(1-1e-8,pred.p_home))
        # Coefficients predeclared; do not optimize them on 2025-26 holdouts.
        logit=log(prior/(1-prior)) + 0.025*margin_effect + 0.035*rest_effect
        prob=1/(1+exp(-logit))
        output.append({"game_id":pred.game_id,"season":season,"p_home":prob,
                       "dual_eligible":dual_eligible(prob),
                       "n_home":len(history[h]),"n_away":len(history[a]),
                       "rolling_margin_delta":round(margin_effect,4),
                       "rest_delta":rest_effect})
        hp,ap=row["home_points"],row["away_points"]
        if hp is not None and ap is not None:
            if h in last_day and day<last_day[h] or a in last_day and day<last_day[a]:
                raise ValueError("Nonchronological team history")
            margin=float(hp)-float(ap)
            history[h].append(max(-30,min(30,margin)))
            history[a].append(max(-30,min(30,-margin)))
            last_day[h]=day;last_day[a]=day
    return output

def compare(games):
    games=sorted(games,key=lambda r:(r["tipoff_utc"],str(r["game_id"])))
    base=list(evaluate(games,season_min=2024,season_max=2026))
    challenger=predict_challenger(games)
    result={}
    for season in (2025,2026):
        pairs=[(g,b,c) for g,b,c in zip(games,base,challenger) if int(g["season"])==season]
        if len(pairs)!=1230:raise ValueError(f"Incomplete holdout {season}")
        def measure(which):
            from math import log,log1p
            ps=[max(1e-12,min(1-1e-12,(b.p_home if which=="elo" else c["p_home"]))) for g,b,c in pairs]
            ys=[int(g["home_points"]>g["away_points"]) for g,b,c in pairs]
            n=len(ps)
            return {"brier":sum((p-y)**2 for p,y in zip(ps,ys))/n,
                    "log_loss":-sum(y*log(p)+(1-y)*log1p(-p) for p,y in zip(ps,ys))/n}
        result[str(season)]={"games":len(pairs),"elo":measure("elo"),"challenger":measure("challenger")}
        result[str(season)]["challenger_better_on_both"]=all(result[str(season)]["challenger"][m]<result[str(season)]["elo"][m] for m in ("brier","log_loss"))
    result["candidate_only"]=True
    result["accepted_for_production"]=False
    result["coefficients"]={"rolling_margin_logit":0.025,"rest_day_logit":0.035}
    return result
