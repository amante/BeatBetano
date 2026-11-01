"""#274: full official schedule-day slate, with explicit no-forecast rows.

Never drop started, blocked or unmatched games from the daily presentation.
This is an experimental outcome-only display, not a goalie scenario forecast.
"""
import argparse,json
from pathlib import Path
from nhl.historical_target_walkforward import CATEGORIES
from nhl.pulso_pregame_v7 import parse_utc

def build(schedule,report,forecast_dir):
 fixtures=schedule["fixtures"]
 if not isinstance(fixtures,list) or len({str(f["game_id"]) for f in fixtures})!=len(fixtures):
  raise ValueError("Invalid or duplicate official fixtures")
 requested={str(f["game_id"]):f for f in fixtures}
 eligible={str(f["game_id"]):f for f in report["games"]}
 if not set(eligible)<=set(requested):raise ValueError("Unverified prospective game")
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Research provenance missing")
 forecasts={}
 for path in Path(forecast_dir).glob("*.json"):
  item=json.loads(path.read_text());r=item["record"];gid=str(r["game_id"])
  if gid not in eligible or r["market"] not in CATEGORIES:raise ValueError("Unexpected research forecast")
  if (gid,r["market"]) in forecasts:raise ValueError("Duplicate frozen market")
  if r.get("official") is not False or r.get("odds_used_in_model") is not False:raise ValueError("Wrong forecast status")
  from nhl.pulso_collective_audit_208 import freeze_prediction
  expected=freeze_prediction(r)
  if item.get("frozen") is not True or item.get("sha256")!=expected["sha256"]:raise ValueError("Broken digest")
  if any(str(r[k])!=str(eligible[gid][k]) for k in ("home","away","start_utc")):raise ValueError("Fixture mismatch")
  forecasts[(gid,r["market"])]=r
 games=[]
 for f in sorted(fixtures,key=lambda x:(x["scheduled_start"],str(x["game_id"]))):
  gid=str(f["game_id"]);markets={m:forecasts[(gid,m)]["probabilities"] for m in CATEGORIES if (gid,m) in forecasts}
  if markets and set(markets)!=set(CATEGORIES):raise ValueError("Partial forecast would hide market")
  if markets:
   state="experimental_forecast"
  elif gid not in eligible:
   state="not_pregame_at_capture"
  else:
   state="pregame_forecast_unavailable"
  games.append({"game_id":gid,"home":f["home"],"away":f["away"],
                "start_utc":f["scheduled_start"],"game_state_at_capture":f["game_state"],
                "forecast_status":state,"markets":markets if markets else None,
                "official":False,"goalie_conditioned":False})
 return {"kind":"nhl_daily_complete_slate_274","date":report["date"],
         "schedule_source_url":schedule["source_url"],"schedule_captured_at":schedule["captured_at"],
         "official_schedule_games":len(games),"experimental_predicted_games":sum(g["forecast_status"]=="experimental_forecast" for g in games),
         "not_pregame_at_capture":sum(g["forecast_status"]=="not_pregame_at_capture" for g in games),
         "pregame_forecast_unavailable":sum(g["forecast_status"]=="pregame_forecast_unavailable" for g in games),
         "games":games,"official":False,"odds_used":False,
         "note":"Complete official schedule-day coverage, including games already started. No retrospective prediction."}
def main():
 p=argparse.ArgumentParser()
 for flag in ("schedule","report","forecast-dir","out"):p.add_argument("--"+flag,required=True)
 a=p.parse_args();result=build(json.loads(Path(a.schedule).read_text()),
      json.loads(Path(a.report).read_text()),a.forecast_dir)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:result[k] for k in ("official_schedule_games","experimental_predicted_games","not_pregame_at_capture","pregame_forecast_unavailable")}))
if __name__=="__main__":main()
