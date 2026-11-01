"""#270: independent feature-group ablation on identical held-out NHL games."""
import argparse,json
from pathlib import Path
from nhl.pulso_goalie_model_269 import split,train,predict,logit,score,vector,FEATURES

GROUPS={"constant":(),"teams":(2,3),"goalies":(0,1),"combined":(0,1,2,3)}
def assess(report):
    if report.get("kind")!="nhl_historical_goalie_features_267" or report.get("source_game_count")!=2811 or not report.get("batch_report",{}).get("complete_source_coverage") or report.get("odds_used") is not False:raise ValueError("Unverified dataset")
    rows=report["eligible_rows"]
    if len(rows)!=report["eligible_count"] or len({str(r["game_id"]) for r in rows})!=len(rows):raise ValueError("Duplicate or missing rows")
    if any(not r["feature_as_of_date"]<r["date"] for r in rows):raise ValueError("Leakage")
    fit,val,test=split(rows)[0]
    if min(map(len,(fit,val,test)))<100:raise ValueError("Insufficient history")
    outcome=lambda group:[int(r["ml_winner"]=="home") for r in group]
    features=lambda group,cols:[[vector(r)[i] for i in cols] for r in group]
    results={}
    for name,cols in GROUPS.items():
        if not cols:
            prior=(sum(outcome(fit))+.5)/(len(fit)+1)
            predictions=[prior]*len(test)
            results[name]={"holdout":score(predictions,outcome(test)),"calibrated":False}
        else:
            model=train(features(fit,cols),outcome(fit))
            rawval=[predict(model,x) for x in features(val,cols)]
            calibrator=train([[logit(p)] for p in rawval],outcome(val),l2=.005)
            rawtest=[predict(model,x) for x in features(test,cols)]
            calibrated=[predict(calibrator,[logit(p)]) for p in rawtest]
            results[name]={"holdout":score(calibrated,outcome(test)),
                           "uncalibrated_holdout":score(rawtest,outcome(test)),
                           "calibrated":True}
    combined=results["combined"]["holdout"]
    teams=results["teams"]["holdout"]
    return {"kind":"nhl_goalie_ablation_270","fit_n":len(fit),"validation_n":len(val),"holdout_n":len(test),
            "groups":results,"goalie_incremental_brier":round(teams["brier"]-combined["brier"],6),
            "goalie_incremental_log_loss":round(teams["log_loss"]-combined["log_loss"],6),
            "beats_team_only_both":combined["brier"]<teams["brier"] and combined["log_loss"]<teams["log_loss"],
            "official_predictions":0,"automatic_promotion":False,"odds_used":False,
            "note":"Four-group ablation against identical holdout. Stronger #218 baseline still requires aligned matchup-level prediction comparison."}
def main():
    p=argparse.ArgumentParser();p.add_argument("--features",required=True);p.add_argument("--out",required=True)
    args=p.parse_args();r=assess(json.loads(Path(args.features).read_text()))
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2))
    print(json.dumps({k:r[k] for k in ("holdout_n","goalie_incremental_brier","goalie_incremental_log_loss","beats_team_only_both")}))
if __name__=="__main__":main()
