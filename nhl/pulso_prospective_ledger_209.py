"""Append-only prospective evidence ledger; never infer official picks from readiness."""
import argparse,hashlib,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def archive(report,output_dir,run_id):
 if not str(run_id).isdigit():raise ValueError("Numeric run id required")
 issued=parse_utc(report["generated_at_utc"])
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Only verified source readiness supported at this stage")
 for game in report["games"]:
  if game.get("probabilities") is not None or game.get("official") is not False:raise ValueError("Unexpected predicted game")
  if parse_utc(game["start_utc"])<=issued:raise ValueError("Late capture would contaminate ledger")
 path=Path(output_dir)/("run-"+str(run_id)+".json")
 if path.exists():raise FileExistsError("Append-only ledger run exists")
 payload={"run_id":str(run_id),"source_report":report}
 encoded=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
 result={"sha256":hashlib.sha256(encoded).hexdigest(),"payload":payload,
         "immutable_by_policy":True,"storage":"git append-only filename; protected branch permissions required"}
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
 return path
def main():
 p=argparse.ArgumentParser();p.add_argument("--report",required=True);p.add_argument("--output-dir",required=True);p.add_argument("--run-id",required=True)
 a=p.parse_args();print(archive(json.loads(Path(a.report).read_text()),a.output_dir,a.run_id))
if __name__=="__main__":main()
