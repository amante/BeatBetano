"""NHL chronological, leakage-free ML validation from completed official NHL games.

All features are constructed using games strictly earlier than the target.
No bookmaker data. No retrospective full-season totals.
"""
import argparse,json,math
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path
import requests

API="https://api-web.nhle.com/v1/score/"
def parse_games(payload,day):
    rows=[]
    for g in payload.get("games",[]):
        if g.get("gameType")!=2 or g.get("gameState") not in ("FINAL","OFF"):
            continue
        h=g.get("homeTeam",{});a=g.get("awayTeam",{})
        if not all(isinstance(t.get("score"),int) and isinstance(t.get("abbrev"),str) for t in (h,a)):
            continue
        if h["score"]==a["score"]:continue
        rows.append({"date":day,"id":str(g["id"]),"home":h["abbrev"],"away":a["abbrev"],
                     "hg":h["score"],"ag":a["score"]})
    return rows

def fetch_season(fetch,start,end,pause=lambda:None):
    # NHL schedule API returns an entire schedule week; fewer requests than
    # one per calendar day. Overlap and holidays handled by game ID dedup.
    games_by_id={};errors=[]
    current=start
    while current<=end:
        anchor=current.isoformat()
        try:
            response=fetch("https://api-web.nhle.com/v1/schedule/"+anchor)
            response.raise_for_status()
            payload=response.json()
            if not isinstance(payload.get("gameWeek"),list):
                raise ValueError("Missing gameWeek; API schema changed")
            for day in payload["gameWeek"]:
                game_date=day.get("date")
                if not game_date or not start.isoformat()<=game_date<=end.isoformat():
                    continue
                for g in parse_games({"games":day.get("games",[])},game_date):
                    games_by_id[g["id"]]=g
        except (requests.RequestException,ValueError,KeyError) as exc:
            errors.append({"date":anchor,"error":str(exc)[:120]})
        pause()
        current+=timedelta(days=7)
    return sorted(games_by_id.values(),key=lambda x:(x["date"],x["id"])),errors

def poisson(mean):
    xs=[math.exp(-mean)]
    for n in range(1,24):xs.append(xs[-1]*mean/n)
    xs[-1]+=max(0.,1-sum(xs))
    return xs

def ml(lh,la):
    h=poisson(lh);a=poisson(la)
    win=sum(x*y for i,x in enumerate(h) for j,y in enumerate(a) if i>j)
    loss=sum(x*y for i,x in enumerate(h) for j,y in enumerate(a) if i<j)
    return win+(1-win-loss)/2

def predict(history,game,prior,home_adv,shrink):
    def form(team):
        rows=[x for x in history if team in (x["home"],x["away"])]
        gf=sum(x["hg"] if x["home"]==team else x["ag"] for x in rows)
        ga=sum(x["ag"] if x["home"]==team else x["hg"] for x in rows)
        n=len(rows)
        return (gf+shrink*prior)/(n+shrink),(ga+shrink*prior)/(n+shrink)
    hgf,hga=form(game["home"]);agf,aga=form(game["away"])
    lh=max(.2,min(8.,(hgf+aga)/2*math.exp(home_adv/2)))
    la=max(.2,min(8.,(agf+hga)/2*math.exp(-home_adv/2)))
    return ml(lh,la)

def scores(rows,params,min_prior_games=150):
    # One prediction per game using strictly earlier games; same-day games
    # cannot be used as features for one another.
    prior=[];predictions=[]
    byday=defaultdict(list)
    for row in rows:byday[row["date"]].append(row)
    for day in sorted(byday):
        if len(prior)>=min_prior_games:
            for game in byday[day]:
                p=predict(prior,game,*params)
                y=int(game["hg"]>game["ag"])
                predictions.append({"date":day,"id":game["id"],"p":p,"y":y})
        prior.extend(byday[day])
    if not predictions:return None
    eps=1e-10;n=len(predictions)
    return {"n":n,"brier":sum((r["p"]-r["y"])**2 for r in predictions)/n,
      "log_loss":-sum(r["y"]*math.log(max(eps,r["p"]))+(1-r["y"])*math.log(max(eps,1-r["p"])) for r in predictions)/n,
      "predictions":predictions}

def calibrate(rows,train_until,test_start):
    train=[r for r in rows if r["date"]<=train_until]
    test=[r for r in rows if r["date"]>=test_start]
    if train_until>=test_start:raise ValueError("Train and test windows overlap")
    if len(train)<150 or len(test)<30:raise ValueError("Not enough separated games")
    candidates=[(p,h,s) for p in (2.8,3.0,3.2) for h in (0.0,0.08,0.16) for s in (5,10,20)]
    best=None
    for parameters in candidates:
        result=scores(train,parameters)
        if result and (best is None or result["log_loss"]<best[0]):
            best=(result["log_loss"],parameters)
    if best is None:raise ValueError("Not enough train predictions")
    # Holdout predictions require cumulative historical inputs; never train
    # on holdout outcome for the same day, but earlier holdout days may enter form.
    combined=scores(rows,best[1])
    predictions=[r for r in combined["predictions"] if r["date"]>=test_start]
    if len(predictions)!=len(test):raise ValueError("Incomplete holdout coverage")
    n=len(predictions)
    brier=sum((r["p"]-r["y"])**2 for r in predictions)/n
    logloss=-sum(r["y"]*math.log(r["p"])+(1-r["y"])*math.log(1-r["p"]) for r in predictions)/n
    return {"train_games":len(train),"test_games":n,"selected_parameters":{"prior_goals":best[1][0],
         "home_log_adjustment":best[1][1],"shrink_games":best[1][2]},
         "holdout_brier":round(brier,6),"holdout_log_loss":round(logloss,6),
         "neutral_brier":round(sum((.5-r["y"])**2 for r in predictions)/n,6),
         "neutral_log_loss":round(math.log(2),6),
         "holdout_predictions":predictions,"validated_out_of_sample":True,
         "model_scope":"simplified_completed_game_ml_only",
         "not_validated":["regulation","three_goal_lead","goalie","pp_pk","injuries","challenger"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2024-10-01")
    p.add_argument("--end",default="2026-10-26")
    p.add_argument("--train-through",default="2025-06-30")
    p.add_argument("--test-from",default="2025-10-01")
    p.add_argument("--output",required=True);p.add_argument("--summary",required=True)
    a=p.parse_args();session=requests.Session()
    games,errors=fetch_season(lambda url:session.get(url,timeout=20),date.fromisoformat(a.start),date.fromisoformat(a.end))
    if len(errors)>0:raise SystemExit(f"Historical retrieval incomplete: {len(errors)} failed weeks. Refusing false validation.")
    if len(games)<1500:raise SystemExit(f"Insufficient completed games: {len(games)}. Refusing false validation.")
    result=calibrate(games,a.train_through,a.test_from)
    result["retrieved_games"]=len(games);result["historical_days_errors"]=errors
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
    md="## NHL real walk-forward ML calibration\\n\\n"+json.dumps({k:v for k,v in result.items() if k!="holdout_predictions"},indent=2)+"\\n"
    summary=Path(a.summary);summary.parent.mkdir(parents=True,exist_ok=True);summary.write_text(md.replace("\\n","\n"))
    print(json.dumps({k:v for k,v in result.items() if k!="holdout_predictions"}))
if __name__=="__main__":main()
