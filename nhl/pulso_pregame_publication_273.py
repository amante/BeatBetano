"""#273: validate frozen #218 research forecasts before publishing their web index."""
import argparse,json,math,hashlib
from collections import defaultdict
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES
from nhl.pulso_pregame_v7 import parse_utc

def audit(report,forecast_dir):
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:raise ValueError("Unverified source report")
 fixtures={str(f["game_id"]):f for f in report["games"]}
 if len(fixtures)!=len(report["games"]):raise ValueError("Duplicate fixture")
 rows=list(Path(forecast_dir).glob("*.json"))
 bygame=defaultdict(dict)
 for path in rows:
  frozen=json.loads(path.read_text())
  if not isinstance(frozen,dict) or "record" not in frozen:raise ValueError("Non-frozen record")
  r=frozen["record"]
  encoded=json.dumps(r,sort_keys=True,separators=(",",":")).encode()
  if frozen.get("frozen") is not True or frozen.get("sha256")!=hashlib.sha256(encoded).hexdigest():raise ValueError("Broken frozen evidence digest")
  gid=str(r["game_id"]);market=r["market"]
  if gid not in fixtures or market not in CATEGORIES:raise ValueError("Unexpected fixture or market")
  if market in bygame[gid]:raise ValueError("Duplicate market")
  f=fixtures[gid]
  if any(str(r[k])!=str(f[k]) for k in ("home","away","start_utc")):raise ValueError("Fixture identity mismatch")
  if r.get("official") is not False or r.get("odds_used_in_model") is not False or r.get("model_version")!="outcome-only-206-frozen-params":raise ValueError("Wrong research provenance")
  if r.get("point_in_time_sources_verified") is not True:raise ValueError("Source timestamp not verified")
  if not parse_utc(r["prediction_as_of_utc"])<parse_utc(r["start_utc"]):raise ValueError("Prediction not pregame")
  if not parse_utc(r["source_asof_utc"])<=parse_utc(r["prediction_as_of_utc"]):raise ValueError("Source later than forecast")
  if len(str(r.get("historical_labels_sha256","")))!=64:raise ValueError("Unverifiable historical source")
  probs=r["probabilities"]
  if set(probs)!=set(CATEGORIES[market]):raise ValueError("Incomplete market probabilities")
  if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in probs.values()):raise ValueError("Invalid probability")
  if abs(sum(probs.values())-1)>1e-6:raise ValueError("Market probabilities not normalized")
  bygame[gid][market]=r
 for gid,markets in bygame.items():
  if set(markets)!=set(CATEGORIES):raise ValueError("Incomplete markets for predicted game")
  if len({markets[m]["prediction_as_of_utc"] for m in markets})!=1:raise ValueError("Inconsistent forecast timestamps")
 return {"kind":"nhl_pregame_publication_audit_273","source_fixture_count":len(fixtures),
         "predicted_fixture_count":len(bygame),"frozen_forecasts":len(rows),
         "markets_per_predicted_fixture":len(CATEGORIES),"publication_type":"experimental_outcome_only",
         "official_predictions":0,"odds_used":False,"full_model_validated":False,
         "goalie_conditioned":False,"audit_passed":True,
         "note":"Zero predicted fixtures allowed if all games already started. No goalie-specific or official model claims."}
def main():
 p=argparse.ArgumentParser()
 for flag in ("report","forecast-dir","out"):p.add_argument("--"+flag,required=True)
 a=p.parse_args();r=audit(json.loads(Path(a.report).read_text()),a.forecast_dir)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,indent=2))
 print(json.dumps(r))
if __name__=="__main__":main()
