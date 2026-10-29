"""Retrospective walk-forward test of prior-date TEAM goalie evidence.

Important: historical goalie ID rates are pooled by team, NOT a forecast of
the unobserved next starting goalie. Holdout 2026-03 onward was inspected in
prior research; this is NOT an independent prospective validation.
"""
import argparse,json,math
from pathlib import Path
try:
 from nhl.historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START
except ModuleNotFoundError:
 from historical_target_walkforward import read_labels,timeline,TUNE_START,TUNE_END,TEST_START

def logit(p):return math.log(max(1e-9,p)/max(1e-9,1-p))
def logistic(z):return 1/(1+math.exp(-max(-30,min(30,z))))
def history_signal(r,side,min_games=3):
 players=r[side]["players"]
 valid=[p for p in players.values() if p.get("role")=="goalie" and p.get("goalie_games",0)>=min_games and p.get("goalie_shots",0)>0]
 if not valid:return None
 saves=sum(p["goalie_saves"] for p in valid);shots=sum(p["goalie_shots"] for p in valid)
 if shots<=0 or saves<0 or saves>shots:raise ValueError("Invalid goalie records")
 return (saves+90.5)/(shots+100)
def score(rows,coef):
 losses=[]
 for r in rows:
  p=r["base"]
  if r["signal"] is not None:p=logistic(logit(p)+coef*r["signal"])
  y=r["y"]
  losses.append(((p-y)**2,-math.log(max(1e-12,p if y else 1-p)),p,y))
 return {"n":len(rows),"coverage":sum(r["signal"] is not None for r in rows),
  "brier":round(sum(x[0] for x in losses)/len(losses),6),
  "log_loss":round(sum(x[1] for x in losses)/len(losses),6),
  "calibration_bins":[{"bin":i,"n":len(v),
     "mean_pred":round(sum(x[2] for x in v)/len(v),6) if v else None,
     "observed":round(sum(x[3] for x in v)/len(v),6) if v else None}
   for i in range(10) for v in [[x for x in losses if min(9,int(x[2]*10))==i]]]}
def evaluate(labels,history):
 index={r["game_id"]:r for r in history}
 if len(index)!=len(history) or len(history)!=len(labels):raise ValueError("History/label count mismatch")
 base={r["game_id"]:r for r in timeline(labels,80,.5)}
 joined=[]
 for r in labels:
  h=index.get(r["game_id"])
  if h is None or h["date"]!=r["date"] or h["home"]["team"]!=r["home"] or h["away"]["team"]!=r["away"]:
   raise ValueError("Fixture history mismatch")
  if h.get("data_class")!="previous_dates_postgame_player_observations":raise ValueError("Not prior-date history")
  home=history_signal(h,"home");away=history_signal(h,"away")
  joined.append({"game_id":r["game_id"],"date":r["date"],"base":base[r["game_id"]]["probs"]["ml"][0],
   "y":int(r["ml_winner"]=="home"),"signal":(home-away) if home is not None and away is not None else None})
 tune=[r for r in joined if TUNE_START<=r["date"]<=TUNE_END]
 test=[r for r in joined if r["date"]>=TEST_START]
 if len(tune)<200 or len(test)<100:raise ValueError("Insufficient research splits")
 selected=min((0.,1.,2.,4.,8.),key=lambda k:(score(tune,k)["log_loss"],k))
 return {"games":len(labels),"tune_n":len(tune),"test_n":len(test),"tune_window":[TUNE_START,TUNE_END],
  "test_from":TEST_START,"goalie_coefficient_selected_from_tune":selected,
  "tune_baseline":score(tune,0.),"tune_challenger":score(tune,selected),
  "holdout_baseline":score(test,0.),"holdout_challenger":score(test,selected),
  "goalie_feature":"difference of TEAM pooled prior-date goalie save percentages, shrunk with 100 pseudo shots / 90.5 saves",
  "no_starter_identity_assumed":True,
  "holdout_previously_inspected":True,"independent_out_of_sample_validation":False,
  "not_actual_goalie_daily_rating":True,"odds_used":False,"model_promoted":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--labels",required=True);p.add_argument("--history",required=True);p.add_argument("--output",required=True)
 a=p.parse_args();result=evaluate(read_labels(a.labels),json.loads(Path(a.history).read_text()))
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:result[k] for k in ("test_n","goalie_coefficient_selected_from_tune","holdout_baseline","holdout_challenger")},indent=2))
if __name__=="__main__":main()
