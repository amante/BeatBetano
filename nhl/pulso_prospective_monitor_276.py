"""#276: append-only prospective forecast snapshots and postgame scoring.

Only score completed games with externally supplied, independently checked
official labels. Never infer actual outcomes from a model prediction.
"""
import argparse,hashlib,json,math
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES
from nhl.pulso_pregame_v7 import parse_utc

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def freeze(slate,run_id,destination):
 if not str(run_id).isdigit():raise ValueError("Run ID must be numeric")
 if slate.get("kind")!="nhl_research_daily_presentation_275" or slate.get("official") is not False or slate.get("odds_used") is not False:raise ValueError("Not research predictions")
 if len(slate["games"])!=slate["official_schedule_games"] or len({g["game_id"] for g in slate["games"]})!=len(slate["games"]):raise ValueError("Incomplete slate")
 path=Path(destination)/("run-"+str(run_id)+".json")
 if path.exists():raise FileExistsError("Run snapshot must remain immutable")
 record={"kind":"nhl_prospective_snapshot_276","run_id":str(run_id),"date":slate["date"],
         "slate":slate,"slate_sha256":digest(slate),"official":False}
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(record,indent=2))
 return record
def score(snapshot,results):
 if snapshot.get("kind")!="nhl_prospective_snapshot_276" or digest(snapshot["slate"])!=snapshot.get("slate_sha256"):raise ValueError("Broken prospective hash")
 if results.get("kind")!="nhl_official_final_labels" or results.get("source_url","").startswith("https://")==False:raise ValueError("Official result provenance required")
 if not results.get("source_as_of_utc"):raise ValueError("Result timestamp missing")
 actual={str(g["game_id"]):g for g in results["games"]}
 if len(actual)!=len(results["games"]):raise ValueError("Duplicate result")
 scores={m:[] for m in CATEGORIES}
 pending=0;complete=0
 for fixture in snapshot["slate"]["games"]:
  if fixture["status"]!="experimental_forecast":continue
  game=actual.get(str(fixture["game_id"]))
  if game is None:pending+=1;continue
  if game.get("game_state") not in ("OFF","FINAL"):raise ValueError("Unfinished game labeled final")
  if game.get("home")!=fixture["home"] or game.get("away")!=fixture["away"]:raise ValueError("Mismatched result identity")
  if not parse_utc(results["source_as_of_utc"])>parse_utc(fixture["start_utc"]):raise ValueError("Result captured before start")
  y=game.get("outcomes",{})
  if set(y)!=set(CATEGORIES):raise ValueError("Missing final markets")
  probs={"ml":fixture["ml"],"rt":fixture["rt"],
    "home3":{"yes":fixture["home_plus3"],"no":1-fixture["home_plus3"]},
    "away3":{"yes":fixture["away_plus3"],"no":1-fixture["away_plus3"]},
    "first3":fixture["first_to_plus3"]}
  for m,cats in CATEGORIES.items():
   if y[m] not in cats:raise ValueError("Invalid final outcome")
   p=probs[m]
   if set(p)!=set(cats) or abs(sum(p.values())-1)>1e-6:raise ValueError("Invalid probability")
   scores[m].append((sum((p[c]-float(c==y[m]))**2 for c in cats)/len(cats),
                  -math.log(max(1e-12,p[y[m]]))))
  complete+=1
 return {"kind":"nhl_prospective_scorecard_276","snapshot_run_id":snapshot["run_id"],"snapshot_sha256":snapshot["slate_sha256"],
    "source_url":results["source_url"],"graded_games":complete,"pending_games":pending,
    "markets":{m:{"n":len(vals),"brier":round(sum(x[0] for x in vals)/len(vals),6) if vals else None,
      "log_loss":round(sum(x[1] for x in vals)/len(vals),6) if vals else None} for m,vals in scores.items()},
    "automatic_promotion":False,"official_predictions":0,"status":"research_only"}
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="action",required=True)
 f=sub.add_parser("freeze");f.add_argument("--slate",required=True);f.add_argument("--run-id",required=True);f.add_argument("--out-dir",required=True)
 s=sub.add_parser("score");s.add_argument("--snapshot",required=True);s.add_argument("--results",required=True);s.add_argument("--out",required=True)
 args=p.parse_args()
 if args.action=="freeze":
  result=freeze(json.loads(Path(args.slate).read_text()),args.run_id,args.out_dir)
 else:
  result=score(json.loads(Path(args.snapshot).read_text()),json.loads(Path(args.results).read_text()))
  out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!="slate"}))
if __name__=="__main__":main()
