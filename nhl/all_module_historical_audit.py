"""One-shot evidence-first historical audit for all 14 NHL modules.

Only derive features knowable before the target game. Do not impute missing
starters, injuries, power plays, shots, score paths or referees.
"""
import argparse,json,math
from pathlib import Path
from collections import defaultdict
from datetime import date
from module_validation_readiness import MODULES
from ml_v2_validation import features,probability,TEST_START,TUNE_END

DIVISIONS={
 "Atlantic":"BOS BUF DET FLA MTL OTT TBL TOR",
 "Metropolitan":"CAR CBJ NJD NYI NYR PHI PIT WSH",
 "Central":"CHI COL DAL MIN NSH STL UTA WPG",
 "Pacific":"ANA CGY EDM LAK SEA SJS VAN VGK",
}
DIV={team:division for division,roster in DIVISIONS.items() for team in roster.split()}
RIVALS={frozenset(pair.split("-")) for pair in (
 "BOS-MTL","BOS-TOR","EDM-CGY","PIT-PHI","PIT-WSH",
 "NYR-NYI","NYR-NJD","TOR-OTT","LAK-ANA","VGK-SJS","FLA-TBL")}

def chronological_context(rows):
    byday=defaultdict(list)
    for g in rows:byday[g["date"]].append(g)
    last_played={};output={}
    for day in sorted(byday):
        day_date=date.fromisoformat(day)
        for g in byday[day]:
            home=g["home"];away=g["away"]
            hlast=last_played.get(home);alast=last_played.get(away)
            # Days of rest are fully historical; missing means unknown not rested.
            hrest=(day_date-hlast).days-1 if hlast else None
            arest=(day_date-alast).days-1 if alast else None
            output[g["id"]]={"home_rest_days":hrest,"away_rest_days":arest,
              "rest_difference":hrest-arest if hrest is not None and arest is not None else None,
              "divisional":DIV.get(home) is not None and DIV.get(home)==DIV.get(away),
              "rivalry_registry":frozenset((home,away)) in RIVALS,
              "home_ice":True}
        for g in byday[day]:
            last_played[g["home"]]=day_date
            last_played[g["away"]]=day_date
    return output

def safe_metrics(records,key):
    if not records:return {"n":0,"brier":None,"log_loss":None}
    n=len(records);eps=1e-12
    return {"n":n,
      "brier":round(sum((r[key]-r["actual_home_win"])**2 for r in records)/n,6),
      "log_loss":round(-sum(r["actual_home_win"]*math.log(max(eps,r[key]))+
       (1-r["actual_home_win"])*math.log(max(eps,1-r[key])) for r in records)/n,6),
      "predicted_home":round(sum(r[key] for r in records)/n,4),
      "observed_home":round(sum(r["actual_home_win"] for r in records)/n,4)}

def audit(rows,params=(3.2,.04,20)):
    if len({r["id"] for r in rows})!=len(rows):raise ValueError("Duplicate game IDs")
    if any(r["hg"]==r["ag"] for r in rows):raise ValueError("Completed games require resolved winner")
    context=chronological_context(rows)
    prepared=features(rows)
    records=[]
    for r in prepared:
        if r["date"]<TEST_START:continue
        ctx=context[r["id"]]
        records.append({"date":r["date"],"event_id":r["id"],
          "actual_home_win":r["y"],"p_home":probability(r,*params),**ctx})
    if not records:raise ValueError("No sealed test set")
    groups={
      "all":records,
      "home_rest_advantage":[r for r in records if r["rest_difference"] is not None and r["rest_difference"]>0],
      "home_rest_disadvantage":[r for r in records if r["rest_difference"] is not None and r["rest_difference"]<0],
      "equal_rest":[r for r in records if r["rest_difference"]==0],
      "division":[r for r in records if r["divisional"]],
      "nondivision":[r for r in records if not r["divisional"]],
      "rivalry_registry":[r for r in records if r["rivalry_registry"]],
    }
    status={}
    for name,spec in MODULES.items():
        observed=[]
        if name=="context":observed=["home_ice","rest_days"]
        if name=="division_rivalry":observed=["division","rivalry_registry"]
        missing=[x for x in spec["features"] if x not in observed]
        # Context has partial observed fields but no fitted causal impact.
        status[name]={"status":"partial_observed_not_fitted" if observed else "blocked_missing_historical_data",
            "observed":observed,"missing":missing,
            "validated_effect":False,"outcome_target":spec["target"]}
    return {"as_of_history_max":max(x["date"] for x in rows),
       "test_from":TEST_START,"test_matches":len(records),
       "model_params_source":"ML v2 run 40603042052 (research; not production)",
       "module_status":status,
       "ml_reference_segments":{name:safe_metrics(items,"p_home") for name,items in groups.items()},
       "per_game_context":records,"model_promotion_authorized":False,
       "warning":"Audits 14 modules, but only schedule-derived rest/division/rivalry are historically observable here; no ablation fit or validation of module effects."}

def markdown(r):
    lines=["## NHL — 14 modules historical evidence audit","",
      f"Holdout: {r['test_matches']} games from {r['test_from']}; no bookmaker features.","",
      "| Module | Evidence | Observed | Missing |",
      "|---|---|---|---|"]
    for name,st in r["module_status"].items():
        lines.append(f"| {name} | {st['status']} | {', '.join(st['observed']) or 'none'} | {', '.join(st['missing']) or 'none'} |")
    lines+=["","### ML v2 on historical context segments","",
      "| Segment | N | Brier | Log Loss |",
      "|---|---:|---:|---:|"]
    for name,m in r["ml_reference_segments"].items():
        lines.append(f"| {name} | {m['n']} | {m['brier']} | {m['log_loss']} |")
    lines+=["","**No module effect calibrated. No promotion to official/challenger.**"]
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    for key in ("history","output","summary"):p.add_argument("--"+key,required=True)
    a=p.parse_args()
    report=audit(json.loads(Path(a.history).read_text()))
    for dest,content in ((a.output,json.dumps(report,indent=2)),(a.summary,markdown(report))):
        path=Path(dest);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    print(json.dumps({"modules":len(report["module_status"]),"test_games":report["test_matches"],
     "partial":sum(x["status"]=="partial_observed_not_fitted" for x in report["module_status"].values()),
     "promoted":report["model_promotion_authorized"]}))
if __name__=="__main__":main()
