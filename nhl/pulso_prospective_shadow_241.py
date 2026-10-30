"""PULSO NHL experimental ML challenger prospective shadow forecast.

No odds. Historical TEAM aggregates are NOT starting goalies or verified lineups.
Only fixtures with enough prior-date evidence receive predictions.
"""
import argparse,hashlib,json,math,re,tarfile
from collections import defaultdict
from datetime import datetime,date,timezone
from pathlib import Path,PurePosixPath
from nhl.prior_player_goalie_stats import state,snapshot,extract
from nhl.pulso_sporting_challenger_238 import predict
from nhl.pulso_pregame_v7 import parse_utc

MODEL_RUN_ID=41073894805
MODEL_VERSION="team-ml-challenger-v0-run-41073894805"
def load_history(tar_path,checksums):
 raw=Path(tar_path).read_bytes()
 digest=hashlib.sha256(raw).hexdigest()
 rows=[line.split(maxsplit=1) for line in Path(checksums).read_text().splitlines() if line.strip()]
 matches=[hashval for hashval,name in rows if PurePosixPath(name.lstrip('*')).name==Path(tar_path).name]
 if len(matches)!=1 or matches[0].lower()!=digest:raise ValueError("Historical release SHA256 mismatch")
 games=[];seen=set()
 with tarfile.open(tar_path,"r:gz") as tar:
  for member in tar.getmembers():
   path=PurePosixPath(member.name)
   if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
    raise ValueError("Unsafe archive member")
   if member.isdir():continue
   if not member.name.endswith(".json"):raise ValueError("Unexpected archive member")
   if not re.fullmatch(r"[0-9]{10}\.json",path.name):continue
   f=tar.extractfile(member)
   if f is None:raise ValueError("Unreadable historical game")
   game=json.load(f)
   gid=str(game.get("game_id",""))
   if gid!=path.stem or gid in seen:raise ValueError("Duplicate/mismatched game IDs")
   if not isinstance(game.get("date"),str) or not game.get("home") or not game.get("away"):
    raise ValueError("Missing historical identities")
   seen.add(gid);games.append(game)
 if len(games)!=2811:raise ValueError("Expected exactly 2811 historical games")
 return games,digest

def prior_features(games,as_of_date):
 histories=defaultdict(state);latest={}
 days=defaultdict(list)
 for g in games:
  if g["date"]<as_of_date:days[g["date"]].append(g)
 for d in sorted(days):
  for g in days[d]:
   stats=(g.get("boxscore") or {}).get("player_by_game_stats")
   for side in ("home","away"):
    team=g[side];h=histories[team];h["games"]+=1
    observed=extract(stats,side)
    for typ,count in (("goalie","goalie_games"),("skater","skater_games")):
     z=observed["goalies" if typ=="goalie" else "skaters"]
     if z is None:continue
     h[count]+=1
     for metric in h[typ]:h[typ][metric]+=z[metric]
    latest[team]=d
 return {t:{"features":snapshot(h),"last_game_date":latest.get(t)} for t,h in histories.items()}

def forecast(fixtures,games,trained,issued,min_games=5,max_age_days=210):
 at=parse_utc(issued)
 if trained.get("status")!="research_only_challenger_fitted" or trained.get("promoted") is not False:
  raise ValueError("Expected nonpromoted frozen research model")
 model=trained.get("model",{})
 if model.get("features")!=["team_prior_goalie_sv_diff","team_prior_skater_goals_diff"] or model.get("training_games")!=2182:
  raise ValueError("Unrecognized frozen challenger model provenance")
 if trained.get("training_end","")>at.date().isoformat():raise ValueError("Future-trained model")
 results=[];ids=set()
 for f in fixtures:
  gid=str(f["game_id"])
  if gid in ids:raise ValueError("Duplicate fixture")
  ids.add(gid);start=parse_utc(f["scheduled_start"])
  if start<=at or f.get("game_state") not in ("FUT","PRE"):continue
  d=start.date().isoformat()
  hist=prior_features(games,d)
  teams=[f["home"],f["away"]];evidence=[];reasons=[]
  for team in teams:
   rec=hist.get(team)
   if rec is None:reasons.append(team+":missing_history");continue
   obs=rec["features"];last=rec["last_game_date"]
   age=(start.date()-date.fromisoformat(last)).days
   if age<0:raise ValueError("Postgame feature leakage")
   if age>max_age_days:reasons.append(team+":stale_history")
   if obs["past_games"]<min_games:reasons.append(team+":thin_history")
   if obs["prior_goalie_save_pct"] is None or obs["prior_skater_goals_per_observed_game"] is None:
    reasons.append(team+":missing_core")
   evidence.append({"team":team,"past_games":obs["past_games"],"history_last_date":last,
                    "age_days":age,"team_prior_sv_pct":obs["prior_goalie_save_pct"],
                    "team_prior_scoring":obs["prior_skater_goals_per_observed_game"]})
  probability=None
  if not reasons and len(evidence)==2:
   row={"x":[evidence[0]["team_prior_sv_pct"]-evidence[1]["team_prior_sv_pct"],
             evidence[0]["team_prior_scoring"]-evidence[1]["team_prior_scoring"]]}
   probability=round(predict(model,row),8)
   if not 0<probability<1:raise ValueError("Invalid forecast")
  results.append({"game_id":gid,"date":d,"home":teams[0],"away":teams[1],
    "start_utc":f["scheduled_start"],"prediction_as_of_utc":issued,"model_version":MODEL_VERSION,
    "status":"shadow_prediction" if probability is not None else "blocked",
    "p_home_ml":probability,"p_away_ml":round(1-probability,8) if probability is not None else None,
    "evidence":evidence,"blockers":reasons,"official":False,"odds_used":False,
    "confirmed_starter":False,"lineups_verified":False})
 return {"kind":"prospective_challenger_shadow","model_version":MODEL_VERSION,
   "trained_model_run_id":MODEL_RUN_ID,"generated_at_utc":issued,"games":results,
   "published_forecast_count":sum(r["status"]=="shadow_prediction" for r in results),
   "official":False,"auto_promoted":False,"odds_used":False,
   "limitations":"TEAM aggregate features, not individual goalies, PP/PK or verified current roster. Shadow ML only."}
def main():
 p=argparse.ArgumentParser()
 for key in ("schedule","archive","checksums","trained-model","out"):p.add_argument("--"+key,required=True)
 a=p.parse_args();schedule=json.loads(Path(a.schedule).read_text())
 if not isinstance(schedule.get("fixtures"),list):raise ValueError("Official schedule fixtures required")
 trained=json.loads(Path(a.trained_model).read_text())
 games,digest=load_history(a.archive,a.checksums)
 result=forecast(schedule["fixtures"],games,trained,datetime.now(timezone.utc).isoformat())
 result["historical_release_sha256"]=digest
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"future_games":len(result["games"]),"shadow_ml":result["published_forecast_count"],"blocked":len(result["games"])-result["published_forecast_count"]}))
if __name__=="__main__":main()
