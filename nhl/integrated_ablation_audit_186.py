"""NHL integrated research ablation audit on chronological historical labels.

Only schedule-derived rest/division/rivalry have retrospective pregame coverage.
Historical CRS/unit and ST feed availability is not assumed. These modules are
marked NOT EVALUABLE, not given synthetic zero-effect 'results'.
The holdout has been inspected before: this is research, not independent validation.
"""
import argparse,json,math
from pathlib import Path
try:
 from nhl.historical_target_walkforward import read_labels,timeline,metrics,TUNE_START,TUNE_END,TEST_START
 from nhl.integrated_pregame_research_185_187 import DIV,RIVALS
except ModuleNotFoundError:
 from historical_target_walkforward import read_labels,timeline,metrics,TUNE_START,TUNE_END,TEST_START
 from integrated_pregame_research_185_187 import DIV,RIVALS

from collections import defaultdict
from datetime import date

def context(rows):
 days=defaultdict(list)
 for r in rows:days[r["date"]].append(r)
 last={};out={}
 for day in sorted(days):
  today=date.fromisoformat(day)
  for g in days[day]:
   h,a=g["home"],g["away"]
   hr=(today-last[h]).days-1 if h in last else None
   ar=(today-last[a]).days-1 if a in last else None
   differential=max(-4,min(4,hr-ar)) if hr is not None and ar is not None else 0
   out[g["game_id"]]={"rest":differential,"division":int(DIV.get(h) is not None and DIV[h]==DIV.get(a)),
    "rivalry":int(frozenset((h,a)) in RIVALS),"rest_known":hr is not None and ar is not None}
  for g in days[day]:
   last[g["home"]]=today;last[g["away"]]=today
 return out

def adjust(p,ctx,coefficients):
 x=math.log(max(1e-8,p)/max(1e-8,1-p))
 x+=coefficients[0]*ctx["rest"]+coefficients[1]*ctx["division"]+coefficients[2]*ctx["rivalry"]
 return 1/(1+math.exp(-max(-30,min(30,x))))

GRID=(-0.06,-0.03,0.,0.03,0.06)
CONFIGS={
 "baseline":[(0.,0.,0.)],
 "rest_only":[(r,0.,0.) for r in GRID],
 "division_only":[(0.,d,0.) for d in GRID],
 "rivalry_only":[(0.,0.,v) for v in GRID],
 "all_observable_context":[(r,d,v) for r in GRID for d in GRID for v in GRID],
}
def make_prediction(row,ctx,coef):
 # Context is fitted only for home ML, and away ML is its complement.
 p=adjust(row["probs"]["ml"][0],ctx,coef)
 pred={t:list(v) for t,v in row["probs"].items()}
 pred["ml"]=[p,1.-p]
 return {**row,"probs":pred}
def evaluate(rows):
 if len(rows)!=2811 or len({r["game_id"] for r in rows})!=len(rows):
  raise ValueError("Expected 2811 unique games")
 prepared=timeline(rows,80,.5)
 contexts=context(rows)
 tune=[r for r in prepared if TUNE_START<=r["date"]<=TUNE_END]
 hold=[r for r in prepared if r["date"]>=TEST_START]
 if len(tune)<200 or len(hold)<100:raise ValueError("Insufficient tune/holdout")
 def aggregate(source,coeff):
  return metrics([make_prediction(r,contexts[r["game_id"]],coeff) for r in source])
 fits={}
 for name,grid in CONFIGS.items():
  best=min(grid,key=lambda c:(aggregate(tune,c)["ml"]["log_loss"],c))
  fits[name]={"coefficients":list(best),"tune":aggregate(tune,best),
      "holdout":aggregate(hold,best),
      "metrics_note":"ML context adjustment only; RT/First+3/3GLP are identical to baseline"}
 unavailable={}
 for name,required in {
  "special_teams_pp_pk":["dated_pregame_pp_pk_source_by_team_by_game","validated_prior_date_pp_pk"],
  "crs_unit_ratings":["dated_expected_lineup_22_skater_ids_by_fixture","sourced_absences_and_roles","prior_date_unit_evidence"],
  "full_challenger":["all_required_14_module_inputs","trained_joint_coefficients","independent_prospective_holdout"]
 }.items():
  unavailable[name]={"status":"not_evaluable","missing":required,
    "holdout_metrics":None,"no_effect_assumed":False}
 baseline=fits["baseline"]["holdout"]["ml"]
 comparison={name:{"delta_brier":round(v["holdout"]["ml"]["brier"]-baseline["brier"],6),
  "delta_log_loss":round(v["holdout"]["ml"]["log_loss"]-baseline["log_loss"],6)}
  for name,v in fits.items()}
 return {"archive_games":len(rows),"tune_n":len(tune),"holdout_n":len(hold),
  "tune_range":[TUNE_START,TUNE_END],"holdout_from":TEST_START,
  "observable_schedule_ablations":fits,"difference_vs_baseline_ml":comparison,
  "unavailable_ablations":unavailable,
  "feature_policy":"lagged NHL outcome counts and previously observed fixture dates; no future game statistics",
  "baseline_params":{"shrink":80,"team_weight":.5},
  "previously_examined_holdout":True,"independent_prospective_validation":False,
  "model_promoted":False,"official_14_module_model_executed":False,"odds_used":False}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--labels",required=True);p.add_argument("--output",required=True)
 a=p.parse_args()
 result=evaluate(read_labels(a.labels))
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"holdout_n":result["holdout_n"],
  "ml_differences":result["difference_vs_baseline_ml"],
  "unavailable":list(result["unavailable_ablations"]),
  "promoted":False},indent=2))
if __name__=="__main__":main()
