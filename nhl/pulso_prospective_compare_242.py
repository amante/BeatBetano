"""Point-in-time NHL baseline/challenger paired ML evaluation on official FINAL scores.

Read immutable run-specific forecast files only; never regenerate predictions with results.
Unfinished games remain pending, unmatched games are never scored as paired evidence.
"""
import argparse,json,math,re
from collections import defaultdict
from pathlib import Path
from urllib.request import Request,urlopen
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_pregame_v7 import parse_utc

FINAL={"OFF","FINAL"}
def final_scores(payload):
 if not isinstance(payload.get("games"),list):raise ValueError("Invalid official scoreboard")
 result={}
 for g in payload["games"]:
  state=g.get("gameState")
  if state not in FINAL:continue
  gid=str(g["id"]);home=g.get("homeTeam",{});away=g.get("awayTeam",{})
  if not all((home.get("abbrev"),away.get("abbrev"),isinstance(home.get("score"),int),isinstance(away.get("score"),int))):
   continue
  if home["score"]==away["score"]:continue
  rec={"game_id":gid,"home":home["abbrev"],"away":away["abbrev"],
   "start_utc":g["startTimeUTC"],"y":int(home["score"]>away["score"])}
  if gid in result and result[gid]!=rec:raise ValueError("Conflicting official finals")
  result[gid]=rec
 return result

def collect_baseline(paths):
 collected={}
 for path in sorted(paths):
  envelope=json.loads(Path(path).read_text())
  raw=envelope.get("record",{})
  if raw.get("market")!="ml":continue
  valid=freeze_prediction(raw)
  if envelope.get("sha256")!=valid["sha256"] or envelope.get("frozen") is not True:
   raise ValueError("Invalid frozen baseline integrity")
  if raw.get("official") is not False or raw.get("odds_used_in_model") is not False:
   raise ValueError("Unexpected baseline version")
  gid=str(raw["game_id"]);p=raw["probabilities"]["home"]
  if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<p<1:raise ValueError("Invalid baseline ML")
  if parse_utc(raw["prediction_as_of_utc"])>=parse_utc(raw["start_utc"]):raise ValueError("Baseline after start")
  rec={"model":raw["model_version"],"home":raw["home"],"away":raw["away"],
   "start_utc":raw["start_utc"],"as_of":raw["prediction_as_of_utc"],"p_home":p}
  if gid not in collected or parse_utc(rec["as_of"])<parse_utc(collected[gid]["as_of"]):
   collected[gid]=rec
 return collected

def collect_challenger(paths):
 collected={}
 for path in sorted(paths):
  doc=json.loads(Path(path).read_text())
  if doc.get("kind")!="prospective_challenger_shadow" or doc.get("auto_promoted") is not False:
   raise ValueError("Invalid shadow artifact")
  for g in doc["games"]:
   if g.get("status")!="shadow_prediction":continue
   if g.get("official") is not False or g.get("odds_used") is not False:raise ValueError("Not experimental")
   p=g["p_home_ml"]
   if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<p<1:
    raise ValueError("Invalid challenger probability")
   if parse_utc(g["prediction_as_of_utc"])>=parse_utc(g["start_utc"]):
    raise ValueError("Challenger after puck drop")
   gid=str(g["game_id"])
   rec={"model":g["model_version"],"home":g["home"],"away":g["away"],
        "start_utc":g["start_utc"],"as_of":g["prediction_as_of_utc"],"p_home":p}
   if gid not in collected or parse_utc(rec["as_of"])<parse_utc(collected[gid]["as_of"]):
    collected[gid]=rec
 return collected

def evaluate(baseline,challenger,finals):
 paired=[];pending=[];only_baseline=[];only_challenger=[]
 for gid in sorted(set(baseline)|set(challenger)):
  a=baseline.get(gid);b=challenger.get(gid);final=finals.get(gid)
  if not a or not b:
   (only_baseline if a else only_challenger).append(gid);continue
  if a["home"]!=b["home"] or a["away"]!=b["away"] or a["start_utc"]!=b["start_utc"]:
   raise ValueError("Forecast fixture mismatch: "+gid)
  if final is None:
   pending.append(gid);continue
  if any(final[k]!=a[k] for k in ("home","away","start_utc")):
   raise ValueError("Official fixture mismatch: "+gid)
  y=final["y"];x=a["p_home"];z=b["p_home"]
  def loss(p):
   return {"brier":(p-y)**2,"log_loss":-(y*math.log(p)+(1-y)*math.log(1-p))}
  paired.append({"game_id":gid,"home":a["home"],"away":a["away"],"y_home_win":y,
   "baseline_probability":x,"challenger_probability":z,
   "baseline":loss(x),"challenger":loss(z),
   "baseline_model":a["model"],"challenger_model":b["model"],
   "baseline_frozen_at":a["as_of"],"challenger_frozen_at":b["as_of"]})
 metrics=None
 if paired:
  metrics={k:{"baseline":round(sum(p["baseline"][k] for p in paired)/len(paired),7),
               "challenger":round(sum(p["challenger"][k] for p in paired)/len(paired),7)}
   for k in ("brier","log_loss")}
  for v in metrics.values():v["delta_challenger_minus_baseline"]=round(v["challenger"]-v["baseline"],7)
 return {"status":"prospective_paired_ml_evaluation","paired_completed":len(paired),
   "paired_awaiting_official_final":pending,"unpaired_baseline_only":only_baseline,
   "unpaired_challenger_only":only_challenger,"metrics":metrics,"games":paired,
   "source":"NHL official score API; final only","odds_used":False,"automatic_promotion":False,
   "limitations":"Matching pregame snapshots; provenance is repository run-specific filenames, not independent trusted timestamp attestation."}

def read_official(day):
 if not re.fullmatch(r"20\\d{2}-\\d{2}-\\d{2}",day):raise ValueError("Invalid day")
 url="https://api-web.nhle.com/v1/score/"+day
 with urlopen(Request(url,headers={"User-Agent":"PULSO-NHL-prospective/1.0"}),timeout=25) as f:
  return json.loads(f.read(2000000))
def main():
 p=argparse.ArgumentParser()
 for k in ("baseline-dir","shadow-dir","out"):p.add_argument("--"+k,required=True)
 p.add_argument("--days",nargs="+",required=True)
 a=p.parse_args()
 finals={}
 for day in a.days:
  for gid,result in final_scores(read_official(day)).items():
   if gid in finals and finals[gid]!=result:raise ValueError("Conflicting final game")
   finals[gid]=result
 base=collect_baseline(Path(a.baseline_dir).glob("run-*/*-ml.json"))
 shadow=collect_challenger(Path(a.shadow_dir).glob("run-*/shadow.json"))
 output=evaluate(base,shadow,finals)
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(output,indent=2))
 print(json.dumps({"paired":output["paired_completed"],"pending":len(output["paired_awaiting_official_final"]),"metrics":output["metrics"]},indent=2))
if __name__=="__main__":main()
