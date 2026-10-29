"""PULSO NHL prospective reconciliation: source-readiness vs mature NHL results.

Never promote source readiness to a forecast or treat postgame labels as inputs.
"""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def reconcile(entries,labels):
 by_id={str(x["game_id"]):x for x in labels}
 if len(by_id)!=len(labels):raise ValueError("Duplicate official labels")
 joined=[];status=Counter();seen=set()
 for item in entries:
  record=item.get("payload",{});run=str(record.get("run_id",""))
  report=record.get("source_report",{})
  if not run.isdigit() or not report:raise ValueError("Invalid ledger wrapper")
  freeze=parse_utc(report["generated_at_utc"])
  for game in report.get("games",[]):
   gid=str(game["game_id"]);key=(run,gid)
   if key in seen:raise ValueError("Duplicate capture")
   seen.add(key)
   if parse_utc(game["start_utc"])<=freeze:raise ValueError("Post-start capture")
   if game.get("probabilities") is not None or game.get("official") is not False:raise ValueError("Source-only capture altered")
   label=by_id.get(gid)
   if not label:
    state="awaiting_official_result";outcome=None
   elif label.get("home")!=game["home"] or label.get("away")!=game["away"]:
    state="fixture_identity_conflict";outcome=None
   else:
    state="completed_source_only_no_prediction"
    outcome={"ml":label["ml_winner"],"rt":label["rt_result"],"first3":label["first_to_plus3"],
      "home3":label["home_reached_plus3"],"away3":label["away_reached_plus3"]}
   status[state]+=1
   joined.append({"run_id":run,"game_id":gid,"home":game["home"],"away":game["away"],
     "source_capture_as_of":report["generated_at_utc"],"state":state,
     "outcome":outcome,"forecast":None,"scored":False})
 return {"status":"prospective_source_reconciliation","observations":len(joined),
  "unique_games":len({x["game_id"] for x in joined}),"by_state":dict(status),"rows":joined,
  "metrics":None,"model_promoted":False,
  "note":"Repeated frozen source captures are evidence, not independent predictions. No Brier/ROI without a genuine pregame forecast."}
def main():
 p=argparse.ArgumentParser()
 for k in ("ledger-dir","labels","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args();entries=[]
 for path in sorted(Path(a.ledger_dir).glob("run-*.json")):entries.append(json.loads(path.read_text()))
 with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
 result=reconcile(entries,labels);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:result[k] for k in ("observations","unique_games","by_state")},indent=2))
if __name__=="__main__":main()
