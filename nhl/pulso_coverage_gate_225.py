"""Aggregate actual PULSO pregame source-coverage files; no synthetic training rows."""
import argparse,json
from collections import Counter
from pathlib import Path
from nhl.pulso_evidence_coverage_222_223 import FIELDS
from nhl.pulso_challenger_gate_224 import audit as training_gate

def summarize(reports):
 latest={}
 for report in reports:
  if report.get("kind")!="collective_evidence_coverage":raise ValueError("Invalid coverage report")
  for game in report.get("games",[]):
   gid=str(game["game_id"])
   stamp=game["as_of"]
   if gid not in latest or stamp<latest[gid]["as_of"]:latest[gid]=game
 flags=Counter();rows=0
 for game in latest.values():
  for team in (game["home"],game["away"]):
   v=game["teams"][team]["coverage"]
   if set(v)!=set(FIELDS):raise ValueError("Incomplete coverage schema")
   flags.update({name:1 for name in FIELDS if v[name] is True})
   rows+=1
 coverage={name:{"available":flags[name],"teams":rows,
                "fraction":round(flags[name]/rows,4) if rows else 0.0} for name in FIELDS}
 # Coverage reports are NOT point-in-time attested and labeled train sets.
 empty={"status":"training_dataset_research_only","rows":[]}
 gate=training_gate(empty)
 return {"status":"observed_sporting_coverage","unique_fixtures":len(latest),
  "team_observations":rows,"coverage":coverage,"full_model_ready":sum(
   bool(g["sufficient_for_full_model"]) for g in latest.values()),
  "verified_historical_training_rows":0,"training_gate":gate,
  "challenger_trained":False,"probabilities":None,
  "note":"Only supplied existing coverage reports were counted; historical labels cannot reconstruct pregame features."}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--coverage-dir",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();root=Path(a.coverage_dir)
 reports=[json.loads(path.read_text()) for path in sorted(root.glob("**/collective_coverage.json"))]
 result=summarize(reports)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"unique_fixtures":result["unique_fixtures"],"team_observations":result["team_observations"],
 "full_model_ready":result["full_model_ready"],"gate":result["training_gate"]},indent=2))
if __name__=="__main__":main()
