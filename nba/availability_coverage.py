"""Audit genuine pregame NBA lineup coverage before attempting an impact fit."""
import argparse,json,math
from datetime import datetime,timezone
from pathlib import Path
from availability_ledger import digest,stamp

def audit(archives):
 seen=set();total=complete=eligible=0;reasons={};per_day={}
 for a in archives:
  original={k:v for k,v in a.items() if k!="archive_hash"}
  if a.get("archive_hash")!=digest(original) or a.get("sport")!="nba":
   raise ValueError("Invalid or altered NBA archive")
  for game in a["games"]:
   gid=str(game["game_id"])
   if gid in seen:raise ValueError("Repeated game across archives")
   seen.add(gid);total+=1
   day=game["tipoff_utc"][:10];per_day.setdefault(day,{"total":0,"complete":0})
   per_day[day]["total"]+=1
   if stamp(game["prediction_as_of_utc"])>=stamp(game["tipoff_utc"]):
    raise ValueError("Post-tipoff prediction")
   p=game.get("baseline_p_home")
   if type(p) not in (float,int) or not math.isfinite(p) or not 0<p<1:
    raise ValueError("Missing valid frozen baseline")
   f=game.get("lineup_availability_features",{})
   home=f.get("home_features") if isinstance(f,dict) else None
   away=f.get("away_features") if isinstance(f,dict) else None
   complete_now=(f.get("feature_complete") is True and isinstance(home,dict)
     and isinstance(away,dict) and home.get("verified_starters")==5
     and away.get("verified_starters")==5)
   if complete_now:
    complete+=1;per_day[day]["complete"]+=1
   else:
    for key,bad in (("home_availability_missing",not isinstance(home,dict)),
                    ("away_availability_missing",not isinstance(away,dict)),
                    ("matchup_or_source_incomplete",not f.get("feature_complete"))):
     if bad:reasons[key]=reasons.get(key,0)+1
 return {"sport":"nba","archives":len(archives),"games":total,
  "complete_pregame_features":complete,
  "coverage":round(complete/total,6) if total else None,
  "by_tipoff_day":per_day,"missing_evidence_reasons":reasons,
  "training_rows_authorized":0,"independent_calibration_passed":False,
  "note":"Coverage diagnostic only: no verified historical outcomes or fitted coefficients."}

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",nargs="+",required=True)
 p.add_argument("--output",required=True);args=p.parse_args()
 result=audit([json.loads(Path(f).read_text()) for f in args.input])
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2))
 print(json.dumps({"games":result["games"],"complete":result["complete_pregame_features"],"coverage":result["coverage"]}))
if __name__=="__main__":main()
