"""PULSO #218: prospective fixed-parameter NHL outcome-only baseline.

This is NOT fitted CRS/player/goalie model and never consumes betting odds.
Historical training labels must be available and dated STRICTLY before fixture.
"""
import argparse,csv,hashlib,json,math
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES,outcomes,prediction
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_pregame_v7 import parse_utc

PARAMS={"ml":(80,.5),"rt":(80,.5),"first3":(40,.5),"home3":(8,.5),"away3":(80,.5)}
SOURCE="https://github.com/amante/BeatBetano/releases/tag/nhl-historical-2811-2026"
VERSION="outcome-only-206-rest-context-v1"
REST_LOGIT_COEFFICIENT=0.06
REST_MODULE="schedule_rest"
def _schedule_index(schedule_context,issued):
 if schedule_context is None:return {},None
 if schedule_context.get("kind")!="nhl_official_schedule_context_v1":raise ValueError("Official schedule context required")
 context_asof=parse_utc(schedule_context["as_of_utc"])
 if context_asof>parse_utc(issued):raise ValueError("Schedule context is newer than forecast")
 rows=schedule_context.get("games")
 if not isinstance(rows,list):raise ValueError("Invalid schedule context")
 index={str(r["game_id"]):r for r in rows}
 if len(index)!=len(rows):raise ValueError("Duplicate schedule-context fixture")
 return index,context_asof

def _rest_effect(fixture,context_row,context_asof,issued):
 if context_row is None:return {"module":REST_MODULE,"status":"unavailable","reason":"schedule_context_not_found"}
 if any(str(context_row.get(k))!=str(fixture.get(k)) for k in ("home","away","start_utc")):
  raise ValueError("Schedule context fixture identity mismatch")
 start=parse_utc(fixture["start_utc"])
 sides=context_row.get("teams",{})
 values={}
 for side,team in (("home",fixture["home"]),("away",fixture["away"])):
  item=sides.get(team,{})
  if item.get("status")!="observed_schedule_context":
   return {"module":REST_MODULE,"status":"unavailable","reason":side+"_previous_game_not_confirmed_complete"}
  rest=item.get("rest_days_before_game")
  source=item.get("source") or {}
  try:retrieved=parse_utc(source["retrieved_at"])
  except (KeyError,TypeError,ValueError):return {"module":REST_MODULE,"status":"unavailable","reason":side+"_source_timestamp_missing"}
  if retrieved>parse_utc(issued) or retrieved>=start or context_asof is None or context_asof>=start:
   return {"module":REST_MODULE,"status":"unavailable","reason":side+"_context_not_pregame"}
  if type(rest) is not int or rest<0:
   return {"module":REST_MODULE,"status":"unavailable","reason":side+"_rest_days_missing"}
  values[side]=rest
 delta_days=max(-4,min(4,values["home"]-values["away"]))
 return {"module":REST_MODULE,"status":"applied","feature":"home_rest_days_minus_away_rest_days",
  "home_rest_days":values["home"],"away_rest_days":values["away"],
  "rest_differential_days":delta_days,"coefficient_logit_per_day":REST_LOGIT_COEFFICIENT,
  "logit_adjustment":round(REST_LOGIT_COEFFICIENT*delta_days,6),
  "source_as_of_utc":context_asof.isoformat()}

def generate(fixtures,history,issued,source_sha256,schedule_context=None):
 now=parse_utc(issued)
 schedule_index,context_asof=_schedule_index(schedule_context,issued)
 if len(source_sha256)!=64 or any(c not in "0123456789abcdef" for c in source_sha256):raise ValueError("Invalid verified digest")
 output=[];seen=set()
 for fixture in fixtures:
  gid=str(fixture["game_id"]);start=parse_utc(fixture["start_utc"])
  if gid in seen:raise ValueError("Duplicate fixture")
  seen.add(gid)
  if not now<start:continue
  context_row=schedule_index.get(gid)
  day=(context_row or {}).get("game_date") or fixture.get("game_date") or start.date().isoformat()
  date.fromisoformat(day)
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
  rest=_rest_effect(fixture,context_row,context_asof,issued)
  for market,cats in CATEGORIES.items():
   shrink,weight=PARAMS[market]
   probs=prediction(globals_,teams,fixture["home"],fixture["away"],market,shrink,weight)
   effect={"module":REST_MODULE,"status":"not_used_for_market"}
   if market=="ml":
    p_before=probs[cats.index("home")]
    if rest["status"]=="applied":
     z=math.log(max(1e-12,p_before)/max(1e-12,1-p_before))+rest["logit_adjustment"]
     p_after=1/(1+math.exp(-max(-30,min(30,z))))
     probs=[p_after,1-p_after]
     effect={**rest,"probability_before":round(p_before,8),"probability_after":round(p_after,8),
      "probability_delta_percentage_points":round((p_after-p_before)*100,4)}
    else:effect=rest
   record={"game_id":gid,"home":fixture["home"],"away":fixture["away"],
    "start_utc":fixture["start_utc"],"game_date":day,"prediction_as_of_utc":issued,"source_asof_utc":issued,
    "source_url":SOURCE,"model_version":VERSION,"market":market,
    "probabilities":dict(zip(cats,probs)),"module_effects":{"rest":effect},"odds_used_in_model":False,
    "point_in_time_sources_verified":True,"historical_labels_sha256":source_sha256,
    "historical_prior_date_games":len(eligible),"official":False}
   output.append(freeze_prediction(record))
 return output
def main():
 p=argparse.ArgumentParser()
 for key in ("report","labels","manifest","out-dir"):p.add_argument("--"+key,required=True)
 p.add_argument("--schedule-context")
 a=p.parse_args();report=json.loads(Path(a.report).read_text())
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:raise ValueError("Unverified fixture report")
 path=Path(a.labels);sha=hashlib.sha256(path.read_bytes()).hexdigest()
 manifest=json.loads(Path(a.manifest).read_text())
 if manifest.get("games")!=2811 or manifest.get("sha256")!=sha:raise ValueError("Source digest mismatch")
 with path.open(newline="") as file:rows=list(csv.DictReader(file))
 if len(rows)!=2811:raise ValueError("Incorrect label collection")
 issued=datetime.now(timezone.utc).isoformat()
 schedule_context=json.loads(Path(a.schedule_context).read_text()) if a.schedule_context else None
 frozen=generate(report["games"],rows,issued,sha,schedule_context)
 dest=Path(a.out_dir);dest.mkdir(parents=True,exist_ok=True)
 for f in frozen:
  record=f["record"];name=f'{record["game_id"]}-{record["market"]}.json'
  path=dest/name
  if path.exists():raise FileExistsError(name)
  path.write_text(json.dumps(f,indent=2))
 print(json.dumps({"model_version":VERSION,"fixtures":len({x["record"]["game_id"] for x in frozen}),"frozen_market_forecasts":len(frozen),"official":False}))
if __name__=="__main__":main()
