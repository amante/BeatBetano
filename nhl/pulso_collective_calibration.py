"""PULSO collective outcome probability research: frozen chronological benchmark.

No postgame covariates, player features or market odds. Model trains on labels
from strictly earlier dates. Calibration is assessed on untouched holdout.
"""
import argparse,json,math
from pathlib import Path
from nhl.historical_target_walkforward import (read_labels,timeline,metrics,CATEGORIES,outcomes,
 TUNE_START,TUNE_END,TEST_START)

GRID=[(s,w) for s in (8,20,40,80) for w in (0.,.5,1.)]
def score_by_segment(entries):
 return {"n":len(entries),"metrics":metrics(entries)} if entries else {"n":0,"metrics":None}
def run(rows):
 if len({r["game_id"] for r in rows})!=len(rows):raise ValueError("Duplicate fixture")
 # Importantly optimize separately per target using ONLY an earlier tune window.
 trials={}
 for shrink,w in GRID:
  seq=timeline(rows,shrink,w)
  tune=[r for r in seq if TUNE_START<=r["date"]<=TUNE_END]
  if len(tune)<200:raise ValueError("Insufficient tuning outcomes")
  trials[(shrink,w)]=metrics(tune)
 chosen={}
 for target in CATEGORIES:
  shrink,w=min(GRID,key=lambda sw:(trials[sw][target]["log_loss"],sw[0],sw[1]))
  chosen[target]={"shrink":shrink,"team_weight":w}
 sequences={sw:timeline(rows,*sw) for sw in set(GRID) if sw in set((c["shrink"],c["team_weight"]) for c in chosen.values())}
 baseline=timeline(rows,20,0.)
 hold=[i for i,r in enumerate(baseline) if r["date"]>=TEST_START]
 if len(hold)<100:raise ValueError("Insufficient untouched test games")
 # All sequences generated from same sorted rows and strictly earlier-date labels.
 assembled=[]
 for i in hold:
  b=baseline[i]
  probs={t:sequences[(chosen[t]["shrink"],chosen[t]["team_weight"])][i]["probs"][t] for t in CATEGORIES}
  assembled.append({**b,"probs":probs})
 from collections import defaultdict
 seasons=defaultdict(list)
 for row in assembled:seasons[row["date"][:4]].append(row)
 scores=metrics(assembled);reference=metrics([baseline[i] for i in hold])
 gains={t:{"brier_delta_vs_baseline":round(scores[t]["brier"]-reference[t]["brier"],6),
           "log_loss_delta_vs_baseline":round(scores[t]["log_loss"]-reference[t]["log_loss"],6)} for t in CATEGORIES}
 return {"data_games":len(rows),"test_n":len(hold),
  "tune_window":[TUNE_START,TUNE_END],"test_from":TEST_START,
  "selected_hyperparameters":chosen,"model_scores":scores,"baseline_scores":reference,
  "differences_negative_is_better":gains,
  "holdout_by_year":{s:score_by_segment(es) for s,es in seasons.items()},
  "pregame_feature_coverage":{"player_v5":0,"lineup_asof":0,"goalie_asof":0,"crs":0,"pp_pk":0,
    "note":"These source families are NOT present in historical outcome-only label rows."},
  "train_uses_only_prior_date_labels":True,"odds_used_in_model":False,
  "official_nhl_model":False,"calibrated_for_production":False,
  "automatic_promotion":False,"claims":"Chronological historical-outcome baseline only. Not the player/goalie-enhanced collective model."}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--labels",required=True);p.add_argument("--out",required=True)
 a=p.parse_args()
 result=run(read_labels(a.labels))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
