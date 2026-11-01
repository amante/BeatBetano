"""#272: aligned, chronological head-to-head of teams-only ML and frozen #218 ML.

This is research evidence, not authorization to publish official forecasts.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
from collections import defaultdict
from nhl.pulso_goalie_model_269 import train,predict,logit,score,split,vector
from nhl.historical_target_walkforward import prediction,CATEGORIES
from nhl.pulso_outcome_forecast_218 import PARAMS

def evaluate(report,labels):
 if report.get("kind")!="nhl_historical_goalie_features_267" or report.get("odds_used") is not False or report.get("source_game_count")!=2811 or report.get("batch_report",{}).get("complete_source_coverage") is not True:raise ValueError("Source gate")
 rows=report["eligible_rows"]
 if len(rows)!=report.get("eligible_count") or len({str(r["game_id"]) for r in rows})!=len(rows):raise ValueError("Invalid features")
 if len(labels)!=2811 or len({str(r["game_id"]) for r in labels})!=len(labels):raise ValueError("Label source gate")
 label_by_id={str(r["game_id"]):r for r in labels}
 for r in rows:
  if not r["feature_as_of_date"]<r["date"] or r["ml_winner"] not in ("home","away"):raise ValueError("Leakage or target")
  if str(r["game_id"]) not in label_by_id:raise ValueError("Missing label")
  l=label_by_id[str(r["game_id"])]
  if any(str(l[k])!=str(r[k]) for k in ("date","home","away","ml_winner")):raise ValueError("Label mismatch")
  vector(r)
 fit,val,test=split(rows)[0]
 if min(map(len,(fit,val,test)))<100:raise ValueError("Insufficient holdout")
 xx=lambda group:[[vector(r)[2],vector(r)[3]] for r in group]
 yy=lambda group:[int(r["ml_winner"]=="home") for r in group]
 m=train(xx(fit),yy(fit))
 calibrator=train([[logit(predict(m,x))] for x in xx(val)],yy(val),l2=.005)
 p_ml=[predict(calibrator,[logit(predict(m,x))]) for x in xx(test)]
 # #218: frozen parameters, previous-date historical outcomes only.
 all_by_day=defaultdict(list)
 for l in labels:all_by_day[l["date"]].append(l)
 glob={k:defaultdict(int) for k in CATEGORIES}
 teams=defaultdict(lambda:{k:defaultdict(int) for k in CATEGORIES})
 test_ids={str(r["game_id"]) for r in test};baseline={}
 for day in sorted(all_by_day):
  for l in all_by_day[day]:
   gid=str(l["game_id"])
   if gid in test_ids:
    if not glob["ml"]:raise ValueError("Missing historical prior")
    shrink,weight=PARAMS["ml"]
    baseline[gid]=prediction(glob,teams,l["home"],l["away"],"ml",shrink,weight)[0]
  for l in all_by_day[day]:
   val=l["ml_winner"]
   if val not in ("home","away"):raise ValueError("Bad historical ML")
   glob["ml"][val]+=1
   teams["home:"+l["home"]]["ml"][val]+=1
   teams["away:"+l["away"]]["ml"][val]+=1
 if len(baseline)!=len(test):raise ValueError("Unaligned baseline")
 p218=[baseline[str(r["game_id"])] for r in test]
 teams_metric=score(p_ml,yy(test));ref_metric=score(p218,yy(test))
 bins=[]
 for lo in range(0,10,2):
  included=[(p,y) for p,y in zip(p_ml,yy(test)) if lo/10<=p<(lo+2)/10 or (lo==8 and p==1)]
  bins.append({"range":[lo/10,(lo+2)/10],"n":len(included),
               "mean_prediction":round(sum(p for p,_ in included)/len(included),5) if included else None,
               "observed_home_win":round(sum(y for _,y in included)/len(included),5) if included else None})
 return {"kind":"nhl_strong_baseline_comparison_272","fit_n":len(fit),"validation_n":len(val),"holdout_n":len(test),
         "test_from":min(r["date"] for r in test),"test_through":max(r["date"] for r in test),
         "teams_only_calibrated":teams_metric,"frozen_218":ref_metric,
         "teams_beats_218_both":all(teams_metric[k]<ref_metric[k] for k in ("brier","log_loss")),
         "calibration_bins":bins,"teams_fit":m,"teams_validation_calibrator":calibrator,
         "feature_contract":["home_team_prior_strength","away_team_prior_strength"],
         "point_in_time_live_parity_proven":False,"official_predictions":0,
         "production_approved":False,"odds_used":False,"automatic_promotion":False,
         "notes":"Held-out comparison identical game IDs. Live feature parity must be independently demonstrated before publishing; trained model research-only."}
def main():
 p=argparse.ArgumentParser()
 for key in ("features","labels","out"):p.add_argument("--"+key,required=True)
 a=p.parse_args();labels=list(csv.DictReader(Path(a.labels).open(newline="")))
 r=evaluate(json.loads(Path(a.features).read_text()),labels)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2))
 print(json.dumps({k:r[k] for k in ("holdout_n","teams_only_calibrated","frozen_218","teams_beats_218_both")}))
if __name__=="__main__":main()
