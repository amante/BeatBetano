"""Join verified expected lineup with lagged player-ID goalie/TOI evidence.

Scores are explicit descriptive team skater/offensive and goalie evidence
indices, never NHL win probabilities or official CRS. Unknown evidence fails
closed; current team roster alone never becomes a game lineup.
"""
import argparse,json,math
from pathlib import Path
try:
 from nhl.roster_source_adapter import adapt
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from roster_source_adapter import adapt
 from roster_aware_units import timepoint

def evaluate(history,baseline,expected,prediction_time,min_games=3):
 team=history["team"]
 b=adapt(baseline,team,prediction_time);e=adapt(expected,team,prediction_time)
 if min_games<1:raise ValueError("Invalid minimum games")
 def score(lineup):
  total={"skater_offense":0.,"skater_toi_minutes":0.,"goalie_save_pct_weighted":0.}
  weights={k:0. for k in total};miss={k:[] for k in total}
  for p in lineup["players"]:
   if p["status"]=="out" or p["expected_share"]==0:continue
   pid=str(p["player_id"]);w=p["expected_share"];rec=history["players"].get(pid)
   key="goalie_save_pct_weighted" if p["unit"]=="goalie" else "skater_offense"
   if not rec or rec["role"]!=("goalie" if p["unit"]=="goalie" else "skater"):
    miss[key].append(pid)
    if key=="skater_offense":miss["skater_toi_minutes"].append(pid)
    continue
   if key=="goalie_save_pct_weighted":
    if rec["goalie_games"]>=min_games and rec["goalie_shots"]>0:
     total[key]+=w*rec["goalie_saves"]/rec["goalie_shots"];weights[key]+=w
    else:miss[key].append(pid)
   else:
    if rec["skater_games"]>=min_games:
     total[key]+=w*(rec["skater_goals"]/rec["skater_games"]+.05*rec["skater_shots"]/rec["skater_games"])
     weights[key]+=w
    else:miss[key].append(pid)
    if rec["toi_games"]>=min_games:
     total["skater_toi_minutes"]+=w*rec["toi_seconds"]/rec["toi_games"]/60
     weights["skater_toi_minutes"]+=w
    else:miss["skater_toi_minutes"].append(pid)
  values={k:round(total[k],6) if not miss[k] and weights[k]>0 else None for k in total}
  return {"indices":values,"missing":miss,"observed_weight":weights,"source":lineup["source"],
    "as_of":lineup["as_of"]}
 bs=score(b);es=score(e)
 delta={k:round(es["indices"][k]-bs["indices"][k],6)
   if es["indices"][k] is not None and bs["indices"][k] is not None else None for k in bs["indices"]}
 return {"team":team,"baseline":bs,"expected":es,"availability_delta":delta,
  "full_crs_numeric_rating":None,"full_availability_delta":None,
  "lineup_provenance":"Externally supplied game-specific dated lineup, not official roster membership",
  "limitations":["Skater index is prior-goals + .05 prior-shots weighted by asserted deployment share.",
  "TOI is historical usage, not prospective confirmed minutes.",
  "Goalie index is past saves/shots by identified goalie; no defensive or opponent adjustment.",
  "No validated composite CRS or ML/RT/+3 conversion."],
  "odds_used":False,"official_model_promoted":False}
def main():
 p=argparse.ArgumentParser()
 for arg in ("history","game-id","side","baseline","expected","prediction-time","output"):p.add_argument("--"+arg,required=True)
 a=p.parse_args()
 rows=json.loads(Path(a.history).read_text());r=[x for x in rows if x["game_id"]==a.game_id]
 if len(r)!=1 or a.side not in ("home","away"):raise ValueError("Bad fixture")
 result=evaluate(r[0][a.side],json.loads(Path(a.baseline).read_text()),json.loads(Path(a.expected).read_text()),a.prediction_time)
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"team":result["team"],"indices":result["expected"]["indices"],"delta":result["availability_delta"]},indent=2))
if __name__=="__main__":main()
