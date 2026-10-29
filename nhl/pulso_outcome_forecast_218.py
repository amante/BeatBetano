"""PULSO #218: prospective fixed-parameter NHL outcome-only baseline.

This is NOT fitted CRS/player/goalie model and never consumes betting odds.
Historical training labels must be available and dated STRICTLY before fixture.
"""
import argparse,csv,hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES,outcomes,prediction
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_pregame_v7 import parse_utc

PARAMS={"ml":(80,.5),"rt":(80,.5),"first3":(40,.5),"home3":(8,.5),"away3":(80,.5)}
SOURCE="https://github.com/amante/BeatBetano/releases/tag/nhl-historical-2811-2026"
VERSION="outcome-only-206-frozen-params"
def generate(fixtures,history,issued,source_sha256):
 now=parse_utc(issued)
 if len(source_sha256)!=64 or any(c not in "0123456789abcdef" for c in source_sha256):raise ValueError("Invalid verified digest")
 output=[];seen=set()
 for fixture in fixtures:
  gid=str(fixture["game_id"]);start=parse_utc(fixture["start_utc"])
  if gid in seen:raise ValueError("Duplicate fixture")
  seen.add(gid)
  if not now<start:continue
  day=start.date().isoformat()
  eligible=[r for r in history if r["date"]<day]
  if len(eligible)<200:continue
  globals_={k:defaultdict(int) for k in CATEGORIES}
  teams=defaultdict(lambda:{k:defaultdict(int) for k in CATEGORIES})
  for row in eligible:
   y=outcomes(row)
   for target,value in y.items():
    globals_[target][value]+=1
    teams["home:"+row["home"]][target][value]+=1
    teams["away:"+row["away"]][target][value]+=1
  for market,cats in CATEGORIES.items():
   shrink,weight=PARAMS[market]
   probs=prediction(globals_,teams,fixture["home"],fixture["away"],market,shrink,weight)
   record={"game_id":gid,"home":fixture["home"],"away":fixture["away"],
    "start_utc":fixture["start_utc"],"prediction_as_of_utc":issued,"source_asof_utc":issued,
    "source_url":SOURCE,"model_version":VERSION,"market":market,
    "probabilities":dict(zip(cats,probs)),"odds_used_in_model":False,
    "point_in_time_sources_verified":True,"historical_labels_sha256":source_sha256,
    "historical_prior_date_games":len(eligible),"official":False}
   output.append(freeze_prediction(record))
 return output
def main():
 p=argparse.ArgumentParser()
 for key in ("report","labels","manifest","out-dir"):p.add_argument("--"+key,required=True)
 a=p.parse_args();report=json.loads(Path(a.report).read_text())
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:raise ValueError("Unverified fixture report")
 path=Path(a.labels);sha=hashlib.sha256(path.read_bytes()).hexdigest()
 manifest=json.loads(Path(a.manifest).read_text())
 if manifest.get("games")!=2811 or manifest.get("sha256")!=sha:raise ValueError("Source digest mismatch")
 with path.open(newline="") as file:rows=list(csv.DictReader(file))
 if len(rows)!=2811:raise ValueError("Incorrect label collection")
 issued=datetime.now(timezone.utc).isoformat()
 frozen=generate(report["games"],rows,issued,sha)
 dest=Path(a.out_dir);dest.mkdir(parents=True,exist_ok=True)
 for f in frozen:
  record=f["record"];name=f'{record["game_id"]}-{record["market"]}.json'
  path=dest/name
  if path.exists():raise FileExistsError(name)
  path.write_text(json.dumps(f,indent=2))
 print(json.dumps({"model_version":VERSION,"fixtures":len({x["record"]["game_id"] for x in frozen}),"frozen_market_forecasts":len(frozen),"official":False}))
if __name__=="__main__":main()
