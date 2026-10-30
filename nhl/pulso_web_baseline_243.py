"""Publish a compact verified experimental baseline ML snapshot for web display."""
import argparse,json
from pathlib import Path
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_pregame_v7 import parse_utc
def build(folder):
 games=[];seen=set()
 for path in sorted(Path(folder).glob("*-ml.json")):
  item=json.loads(path.read_text());raw=item["record"]
  digest=freeze_prediction(raw)["sha256"]
  if item.get("frozen") is not True or item.get("sha256")!=digest:raise ValueError("Tampered baseline")
  if raw["market"]!="ml" or raw["official"] is not False or raw["odds_used_in_model"] is not False:
   raise ValueError("Unsupported baseline")
  gid=str(raw["game_id"])
  if gid in seen:raise ValueError("Repeated game")
  seen.add(gid)
  if parse_utc(raw["prediction_as_of_utc"])>=parse_utc(raw["start_utc"]):raise ValueError("Post-start baseline")
  games.append({"game_id":gid,"home":raw["home"],"away":raw["away"],"start_utc":raw["start_utc"],
    "prediction_as_of_utc":raw["prediction_as_of_utc"],"p_home_ml":raw["probabilities"]["home"],
    "p_away_ml":raw["probabilities"]["away"],"model_version":raw["model_version"]})
 return {"kind":"published_experimental_outcome_baseline","games":games,"official":False,
   "odds_used":False,"limitations":"Fixed outcome-only baseline; not verified full sporting CRS and lineup model"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--forecast-dir",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();result=build(a.forecast_dir)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"baseline_ml_fixtures":len(result["games"])}))
if __name__=="__main__":main()
