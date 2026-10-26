"""Frozen NBA lineup/availability research ledger for true future holdouts.

Never recover alleged pregame starter status from postgame box scores.
"""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone

def stamp(s):
 d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timestamp requires timezone")
 return d.astimezone(timezone.utc)
def digest(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def archive(snapshot,features):
 if snapshot.get("content_sha256")!=features.get("snapshot_sha256"):
  raise ValueError("Mismatched NBA forecast/features")
 freeze=stamp(snapshot["created_at_utc"]);rows=[]
 source=features.get("games",{})
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=stamp(game["tipoff_utc"])
  if freeze>=tip:raise ValueError("After tipoff")
  f=source.get(gid,{})
  rows.append({"game_id":gid,"home_team":game["home_team"],"away_team":game["away_team"],
   "prediction_as_of_utc":snapshot["created_at_utc"],"tipoff_utc":game["tipoff_utc"],
   "baseline_p_home":game.get("hybrid_p_home"),
   "lineup_availability_features":f,
   "feature_complete":f.get("feature_complete") is True,
   "ready_for_fitting":False})
 body={"sport":"nba","schema_version":1,"archive_kind":"frozen_pregame",
       "original_snapshot_hash":snapshot["content_sha256"],"games":rows,
       "postgame_outcomes_included":False}
 body["archive_hash"]=digest(body)
 return body

def join(archive,finished):
 original={k:v for k,v in archive.items() if k!="archive_hash"}
 if digest(original)!=archive.get("archive_hash"):raise ValueError("Tampered archive")
 completed={str(x["game_id"]):x for x in finished.get("games",[])}
 output=[];missing=[]
 for row in archive["games"]:
  gid=row["game_id"];x=completed.get(gid)
  if not x or x.get("status")!="final":
   missing.append(gid);continue
  if (x.get("home_team"),x.get("away_team"))!=(row["home_team"],row["away_team"]):
   raise ValueError("Mismatched teams")
  hs=x.get("home_score");aws=x.get("away_score")
  if type(hs) is not int or type(aws) is not int or hs==aws:raise ValueError("Invalid completed game")
  output.append({"game_id":gid,"home_win":int(hs>aws),"baseline_p_home":row["baseline_p_home"],
   "feature_complete":row["feature_complete"],"archive_hash":archive["archive_hash"]})
 return {"sport":"nba","joined_results":output,"missing_outcomes":missing,
   "independent_impact_validation":False,"authorized_to_adjust_predictions":False}

def main():
 p=argparse.ArgumentParser();p.add_argument("--snapshot");p.add_argument("--features")
 p.add_argument("--archive");p.add_argument("--results");p.add_argument("--output",required=True)
 a=p.parse_args();load=lambda path:json.loads(Path(path).read_text())
 if a.results:
  if not a.archive:raise ValueError("Requires --archive")
  data=join(load(a.archive),load(a.results))
 else:
  if not a.snapshot or not a.features:raise ValueError("Requires snapshot and features")
  data=archive(load(a.snapshot),load(a.features))
 target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
 with target.open("x") as f:json.dump(data,f,indent=2)
 print(json.dumps({"archived":len(data.get("games",[])),"scored":len(data.get("joined_results",[]))}))
if __name__=="__main__":main()
