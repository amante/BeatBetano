"""Conservative teammate-absence-conditioned minute weights.

Only pretip historical games with independently verified absence lists may
contribute to a with/without comparison. Missing context is not 'healthy'.
Output remains experimental; lineup feasibility and actual availability are
separate gates.
"""
import argparse,json,statistics
from pathlib import Path
from datetime import datetime,timezone

def timestamp(s):
 try:
  d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,TypeError):return None

def conditioned_weights(target_tipoff,team,player_ids,absent_ids,games,min_games=3,prior_strength=5):
 tip=timestamp(target_tipoff)
 if tip is None:raise ValueError("Target tipoff must have timezone")
 ids=set(player_ids);absences=set(absent_ids)
 if len(ids)!=len(player_ids) or ids & absences:
  raise ValueError("Duplicate candidates or absent player simultaneously eligible")
 by_player={pid:{"all":[],"conditional":[]} for pid in ids}
 seen=set()
 for game in games:
  if game.get("team")!=team or game.get("availability_verified") is not True:continue
  date=timestamp(game.get("tipoff_utc"))
  if date is None or date>=tip:continue
  gid=str(game.get("game_id") or "")
  if not gid or gid in seen:raise ValueError("Repeated eligible historical game")
  seen.add(gid)
  confirmed=game.get("confirmed_out_player_ids")
  minutes=game.get("player_minutes")
  if not isinstance(confirmed,list) or not isinstance(minutes,dict):continue
  observed_absent=set(map(str,confirmed))
  for pid in ids:
   value=minutes.get(pid)
   if type(value) not in (int,float) or not 0<=value<=60:continue
   by_player[pid]["all"].append(float(value))
   # Require ALL selected missing teammates were absent in this game.
   if absences and absences.issubset(observed_absent):
    by_player[pid]["conditional"].append(float(value))
 result={}
 for pid,values in sorted(by_player.items()):
  baseline=statistics.mean(values["all"]) if len(values["all"])>=min_games else None
  conditional=values["conditional"]
  if baseline is None:
   result[pid]={"weight":None,"status":"insufficient_baseline","sample_games":len(values["all"])}
   continue
  # Shrink noisy with/without difference toward unconditional player baseline.
  delta=statistics.mean(conditional)-baseline if len(conditional)>=min_games else 0
  reliability=len(conditional)/(len(conditional)+prior_strength) if len(conditional)>=min_games else 0
  weight=max(0,min(48,baseline+reliability*delta))
  result[pid]={"weight":round(weight,4),"baseline":round(baseline,4),
    "observed_conditional_games":len(conditional),
    "sample_games":len(values["all"]),"reliability":round(reliability,4),
    "status":"conditional_shrunk" if reliability else "baseline_only_unvalidated_absence_effect"}
 return {"team":team,"weights":result,"absent_player_ids":sorted(absences),
  "method":"verified_prior_event_with_without_shrunk","validated":False,
  "no_odds_input":True,"production_adjustment_authorized":False}
def main():
 p=argparse.ArgumentParser()
 for name in ("history","tipoff","team","players","absent","output"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 hist=json.loads(Path(a.history).read_text())
 out=conditioned_weights(a.tipoff,a.team,a.players.split(","),a.absent.split(",") if a.absent else [],hist["games"])
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2))
 print(json.dumps({"weighted_players":sum(x["weight"] is not None for x in out["weights"].values())}))
if __name__=="__main__":main()
