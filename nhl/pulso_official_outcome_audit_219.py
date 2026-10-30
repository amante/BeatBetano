"""PULSO 219: official NHL play-by-play outcome derivation and frozen forecast audit."""
import argparse,json,urllib.request
from pathlib import Path
from nhl.pulso_forecast_score_217 import evaluate

ENDPOINT="https://api-web.nhle.com/v1/gamecenter/{}/play-by-play"
def label_from_pbp(payload):
 game_id=str(payload["id"]);state=payload.get("gameState")
 if state not in ("OFF","FINAL"):return None
 home=payload["homeTeam"];away=payload["awayTeam"]
 hs=home.get("score");vs=away.get("score")
 if not isinstance(hs,int) or not isinstance(vs,int) or hs==vs:
  raise ValueError("Final score invalid")
 # NHL event snapshots include cumulative homeScore / awayScore per goal event.
 goals=[p for p in payload.get("plays",[]) if p.get("typeDescKey")=="goal"]
 if not goals:raise ValueError("Final game without audited scoring events")
 events=[];prev=(0,0)
 for p in goals:
  period=p.get("periodDescriptor",{}).get("number")
  h=p.get("details",{}).get("homeScore");a=p.get("details",{}).get("awayScore")
  if period is None or not isinstance(h,int) or not isinstance(a,int):
   raise ValueError("Incomplete official goal event")
  if h<prev[0] or a<prev[1] or h+a!=prev[0]+prev[1]+1:
   raise ValueError("Inconsistent chronological goal sequence")
  if period<1:raise ValueError("Invalid period")
  events.append((period,h,a));prev=(h,a)
 if prev!=(hs,vs):
  # Shootout-winning goal contributes to final score but NOT gameplay PBP goals.
  if not (payload.get("gameOutcome",{}).get("lastPeriodType")=="SO"
          and abs(hs-vs)==1 and min(hs,vs)==min(prev)):
   raise ValueError("Final and event scores disagree")
 last_rt=next(((h,a) for period,h,a in reversed(events) if period<=3), (0,0))
 rt="home" if last_rt[0]>last_rt[1] else "away" if last_rt[0]<last_rt[1] else "draw"
 home3=away3=False;first=None
 for _,h,a in events:
  home3|=h-a>=3;away3|=a-h>=3
  if first is None and abs(h-a)>=3:first="home" if h>a else "away"
 return {"game_id":game_id,"home":home["abbrev"],"away":away["abbrev"],
  "ml_winner":"home" if hs>vs else "away","rt_result":rt,
  "first_to_plus3":first or "None","home_reached_plus3":str(home3),"away_reached_plus3":str(away3)}
def fetch_pbp(game_id):
 with urllib.request.urlopen(urllib.request.Request(ENDPOINT.format(game_id),
    headers={"User-Agent":"BeatBetano-Pulso-NHL-Research/1.0"}),timeout=20) as response:
  return json.load(response)
def audit(forecasts,fetch=fetch_pbp):
 ids=sorted({str(x["record"]["game_id"]) for x in forecasts})
 labels=[];pending=[];errors={}
 for gid in ids:
  try:
   label=label_from_pbp(fetch(gid))
   if label is None:pending.append(gid)
   else:labels.append(label)
  except Exception as exc:
   # Never score broken or partial results as if they were official.
   errors[gid]=type(exc).__name__+": "+str(exc)[:140]
 result=evaluate(forecasts,labels)
 result["official_results_retrieved"]=len(labels)
 result["pending_games"]=pending
 result["source_errors"]=errors
 result["source_endpoint_template"]=ENDPOINT
 result["research_only"]=True
 return result
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--forecast-dir",required=True);p.add_argument("--out",required=True)
 a=p.parse_args()
 forecasts=[json.loads(x.read_text()) for x in sorted(Path(a.forecast_dir).glob("**/*.json"))]
 if not forecasts:raise ValueError("No frozen forecast files")
 output=audit(forecasts)
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(output,indent=2))
 print(json.dumps({"scored":output["scored"],"games_official":output["official_results_retrieved"],
  "pending":len(output["pending_games"]),"errors":output["source_errors"],"metrics":output["metrics"]},indent=2))
if __name__=="__main__":main()
