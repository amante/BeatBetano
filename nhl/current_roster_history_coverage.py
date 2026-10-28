"""Join current official roster candidate pools to prior-date player-ID history.

Current membership is NOT a confirmed game lineup. Prior records are strictly
earlier calendar dates than roster fetch, avoiding same-day postgame leakage.
"""
import argparse,json,hashlib
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
try:
 from nhl.individual_goalie_toi_history import entries
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from individual_goalie_toi_history import entries
 from roster_aware_units import timepoint

def aggregate(folder,as_of,expected_count=2811):
 cutoff=timepoint(as_of).astimezone(timezone.utc).date().isoformat()
 paths=list(Path(folder).glob("*.json"))
 if len(paths)!=expected_count:raise ValueError("Historical archive incomplete")
 by_id=defaultdict(lambda:defaultdict(lambda:{"games":0,"toi_games":0,"toi_seconds":0,
      "goalie_games":0,"goalie_saves":0,"goalie_shots":0,"skater_games":0,"skater_goals":0,"skater_shots":0}))
 used=0
 for path in paths:
  game=json.loads(path.read_text())
  if str(game.get("game_id"))!=path.stem:raise ValueError("Invalid game ID")
  if game["date"]>=cutoff:continue
  used+=1
  for side in ("home","away"):
   club=game[side]
   stats=(game.get("boxscore") or {}).get("player_by_game_stats")
   for e in entries(stats,side):
    r=by_id[str(e["id"])][club];r["games"]+=1
    if e["toi_seconds"] is not None:r["toi_games"]+=1;r["toi_seconds"]+=e["toi_seconds"]
    if e["saves_shots"] is not None:
     saves,shots=e["saves_shots"];r["goalie_games"]+=1;r["goalie_saves"]+=saves;r["goalie_shots"]+=shots
    if e["goals"] is not None and e["shots"] is not None and e["shots"]>=e["goals"]:
     r["skater_games"]+=1;r["skater_goals"]+=e["goals"];r["skater_shots"]+=e["shots"]
 return by_id,used

def coverage(rosters,folder,expected_count=2811,min_games=3):
 if len(rosters)!=32 or len({r["team"] for r in rosters})!=32:
  raise ValueError("Expected exactly 32 unique team snapshots")
 # One conservative global cutoff: no archived game on or after the earliest capture day.
 earliest=min(timepoint(r["as_of"]) for r in rosters)
 history,used=aggregate(folder,earliest.isoformat(),expected_count)
 report=[];global_counts=defaultdict(int)
 for team in sorted(rosters,key=lambda x:x["team"]):
  rows=team.get("players",[])
  if not rows or team.get("source_kind")!="official_current_team_roster_not_match_lineup":
   raise ValueError("Not an official current roster candidate pool")
  counts=defaultdict(int);players=[];seen=set()
  for p in rows:
   pid=p["player_id"];role=p["position_group"]
   if pid in seen:raise ValueError("Duplicate player in current roster")
   seen.add(pid)
   hist=history.get(str(pid),{})
   same=hist.get(team["team"],{})
   games=sum(x["games"] for x in hist.values())
   traded=bool(games and any(t!=team["team"] for t in hist))
   current_games=same.get("games",0)
   stat_key="goalie_games" if role=="goalie" else "skater_games"
   own_stat=same.get(stat_key,0)
   all_stat=sum(x[stat_key] for x in hist.values())
   toi=sum(x["toi_games"] for x in hist.values())
   category="same_team" if current_games else ("other_team_only" if games else "no_prior_history")
   counts[category]+=1
   if traded:counts["multiple_or_other_teams"]+=1
   if own_stat>=min_games:counts["same_team_metric_ready"]+=1
   if all_stat>=min_games:counts["cross_team_metric_ready"]+=1
   if toi>=min_games:counts["toi_ready_global"]+=1
   players.append({"player_id":pid,"role":role,"history_category":category,
     "prior_teams":sorted(hist),"prior_games_all_teams":games,
     "prior_games_current_team":current_games,"metric_games_current_team":own_stat,
     "metric_games_all_teams":all_stat,"toi_games_all_teams":toi,
     "possible_transfer_or_prior_other_club":traded,
     "lineup_status":"unknown","starter_confirmed":False})
  counts["roster_players"]=len(players)
  for k,v in counts.items():global_counts[k]+=v
  report.append({"team":team["team"],"roster_as_of":team["as_of"],
    "source_url":team["source_url"],"summary":dict(counts),"players":players})
 return {"historical_games_considered":used,"cutoff_rule":"game_date strictly before earliest roster capture UTC calendar date",
  "min_metric_games":min_games,"teams":report,"total":dict(global_counts),
  "lineups_confirmed":0,"official_model_promoted":False,"odds_used":False,
  "interpretation":"Identity linkage/coverage only. Other-club appearance may reflect trade, historical move or other roster changes; not confirmed transaction."}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--rosters",required=True);p.add_argument("--archive",required=True)
 p.add_argument("--output",required=True);p.add_argument("--expected-games",type=int,default=2811)
 a=p.parse_args();src=Path(a.rosters).read_bytes();rosters=json.loads(src)
 result=coverage(rosters,a.archive,a.expected_games)
 result["rosters_sha256"]=hashlib.sha256(src).hexdigest()
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"historical_games_considered":result["historical_games_considered"],"total":result["total"],
  "teams":len(result["teams"]),"lineups_confirmed":0},indent=2))
if __name__=="__main__":main()
