"""NHL frozen pregame ledger and independent postgame outcome join.

Do NOT reconstruct historical predictions from today's standings, goalie logs,
or results. Archived forecasts are the sole source of pregame features.
"""
import argparse,json,hashlib
from datetime import datetime,timezone
from pathlib import Path
from goalie_holdout import FEATURES,timestamp,validate

def digest(obj):
 return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def freeze(slate,goalies,source_snapshot_ids):
 if slate.get("sport")!="nhl" or goalies.get("sport")!="nhl":raise ValueError("NHL only")
 if slate["as_of_utc"]!=goalies["as_of_utc"]:raise ValueError("Mismatched observations")
 stamp=timestamp(slate["as_of_utc"])
 games=[]
 for g in slate.get("events",[]):
  tip=timestamp(g["start_utc"])
  if not stamp<tip:raise ValueError("Already started")
  eid=str(g["event_id"])
  obs=goalies.get("games",{}).get(eid,{})
  # Archive the raw point-in-time state, even if no starting goalie is known.
  games.append({"event_id":eid,"tipoff_utc":g["start_utc"],
    "prediction_as_of_utc":slate["as_of_utc"],
    "home_team":g["home_team"],"away_team":g["away_team"],
    "statistical_p_home":g.get("statistical_p_home"),
    "goalie_observations":obs,
    "source_snapshot_ids":source_snapshot_ids,
    "starter_confirmed_at_freeze":False,
    "eligible_for_goalie_fit":False})
 body={"schema_version":1,"sport":"nhl","archive_kind":"frozen_pregame",
  "created_at_utc":slate["as_of_utc"],"games":games,
  "postgame_outcomes_included":False,
  "note":"Archive before puck drop. Unknown goalie remains unknown; data cannot be backdated."}
 body["content_sha256"]=digest(body)
 return body

def join(archive,results):
 body={k:v for k,v in archive.items() if k!="content_sha256"}
 if archive.get("content_sha256")!=digest(body):raise ValueError("Tampered archive")
 scores={str(x["event_id"]):x for x in results.get("games",[])}
 output=[];missing=[];seen=set()
 for g in archive["games"]:
  eid=g["event_id"]
  if eid in seen:raise ValueError("Duplicate frozen fixture")
  seen.add(eid)
  x=scores.get(eid)
  if not x or x.get("game_state") not in ("FINAL","OFF"):
   missing.append(eid);continue
  hp=x.get("home_score");ap=x.get("away_score")
  if type(hp) is not int or type(ap) is not int or hp==ap or hp<0 or ap<0:
   raise ValueError("Invalid final NHL score")
  if g["home_team"]!=x.get("home_team") or g["away_team"]!=x.get("away_team"):
   raise ValueError("Postgame team mismatch")
  output.append({"event_id":eid,"home_won":int(hp>ap),
    "home_score":hp,"away_score":ap,
    "tipoff_utc":g["tipoff_utc"],
    "prediction_as_of_utc":g["prediction_as_of_utc"],
    "statistical_p_home":g.get("statistical_p_home"),
    "goalie_snapshot_present":bool(g["goalie_observations"]),
    "eligible_for_goalie_fit":g["eligible_for_goalie_fit"],
    "provenance_hash":archive["content_sha256"]})
 return {"sport":"nhl","joined_results":output,"missing_final_results":missing,
 "training_rows_authorized":0,"historical_goalie_holdout_run":False,
 "note":"Scored factual outcomes; archived goalie features are not automatically verified fitted features."}

def main():
 p=argparse.ArgumentParser();p.add_argument("--slate",required=True)
 p.add_argument("--goalies",required=True);p.add_argument("--output",required=True)
 p.add_argument("--join-results");p.add_argument("--archive")
 a=p.parse_args()
 load=lambda x:json.loads(Path(x).read_text())
 if a.join_results:
  if not a.archive:raise ValueError("--archive needed for join")
  out=join(load(a.archive),load(a.join_results))
 else:
  out=freeze(load(a.slate),load(a.goalies),["nhl_hoy","goalie_observations"])
 target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
 with target.open("x") as f:json.dump(out,f,indent=2)
 print(json.dumps({"archived_games":len(out.get("games",[])),"scored_games":len(out.get("joined_results",[])),"fit_authorized":False}))
if __name__=="__main__":main()
