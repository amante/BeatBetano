"""Score only genuine frozen NHL forecasts against subsequent official labels.

Does not score readiness-only entries and does not manufacture forecasts.
"""
import argparse,csv,hashlib,json
from collections import defaultdict
from pathlib import Path
from nhl.pulso_collective_audit_208 import freeze_prediction,brier,logloss
from nhl.historical_target_walkforward import CATEGORIES

def evaluate(frozen,labels):
 targets={str(x["game_id"]):x for x in labels}
 if len(targets)!=len(labels):raise ValueError("Duplicate target labels")
 rows=[];pending=[];seen=set()
 for envelope in frozen:
  raw=envelope.get("record")
  if not isinstance(raw,dict):raise ValueError("Not a frozen forecast envelope")
  validated=freeze_prediction(raw)
  if envelope.get("sha256")!=validated["sha256"] or envelope.get("frozen") is not True:
   raise ValueError("Forecast integrity mismatch")
  key=(str(raw["game_id"]),raw["model_version"],raw["market"])
  if key in seen:raise ValueError("Multiple predictions for same game, model and market; select frozen version explicitly")
  seen.add(key)
  label=targets.get(str(raw["game_id"]))
  if label is None:
   pending.append({"game_id":raw["game_id"],"market":raw["market"],"model_version":raw["model_version"]})
   continue
  if not raw.get("home") or not raw.get("away") or label["home"]!=raw["home"] or label["away"]!=raw["away"]:
   raise ValueError("Fixture teams disagree with official target")
  category=raw["market"]
  target={"ml":label["ml_winner"],"rt":label["rt_result"],
    "first3":"none" if label["first_to_plus3"] in ("","None",None) else label["first_to_plus3"],
    "home3":"yes" if label["home_reached_plus3"]=="True" else "no",
    "away3":"yes" if label["away_reached_plus3"]=="True" else "no"}[category]
  cats=CATEGORIES[category]
  if target not in cats:raise ValueError("Invalid official target")
  probs=[raw["probabilities"][c] for c in cats]
  rows.append({"game_id":raw["game_id"],"model_version":raw["model_version"],
    "market":category,"brier":brier(probs,target,cats),"log_loss":logloss(probs,target,cats)})
 groups=defaultdict(list)
 for r in rows:groups[(r["model_version"],r["market"])].append(r)
 metrics=[{"model_version":k[0],"market":k[1],"n":len(v),
  "brier":round(sum(x["brier"] for x in v)/len(v),6),
  "log_loss":round(sum(x["log_loss"] for x in v)/len(v),6)} for k,v in sorted(groups.items())]
 return {"status":"prospective_forecast_audit","scored":len(rows),"pending":pending,
  "metrics":metrics,"official_promotion":False,
  "note":"Forecasts must be independently stored before start; SHA256 alone does not attest actual capture time."}
def main():
 p=argparse.ArgumentParser()
 for k in ("forecast-dir","labels","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 envelopes=[json.loads(f.read_text()) for f in sorted(Path(a.forecast_dir).glob("*.json"))]
 with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
 result=evaluate(envelopes,labels)
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"scored":result["scored"],"pending":len(result["pending"]),"metrics":result["metrics"]},indent=2))
if __name__=="__main__":main()
