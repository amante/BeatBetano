"""PULSO #247: fixture-level player/goalie evidence bridge, fail-closed.

Requires game-specific baseline and expected lineups plus prior-date individual
player history. Reuses the existing player-ID scoring module, never invents
lineups from official roster membership or ESPN goalie observations.
"""
import argparse,json
from pathlib import Path
from nhl.expected_lineup_availability import game_report
from nhl.pulso_pregame_v7 import parse_utc

def evaluate_fixture(report,packages):
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Pregame evidence report required")
 capture=parse_utc(report["generated_at_utc"])
 if not isinstance(packages,dict):raise ValueError("Packages must be keyed by fixture ID")
 games=[]
 for f in report["games"]:
  gid=str(f["game_id"])
  if parse_utc(f["start_utc"])<=capture:raise ValueError("Fixture must be pregame")
  item=packages.get(gid,{})
  if not isinstance(item,dict):raise ValueError("Invalid fixture package")
  teams={}
  for team in (f["home"],f["away"]):
   package=item.get(team)
   if package is None:
    teams[team]={"status":"blocked","blockers":["missing_verified_game_lineups_and_player_history"],
      "individual_skater_index":None,"individual_goalie_index":None,"availability_delta":None}
    continue
   if not isinstance(package,dict):raise ValueError("Invalid team evidence")
   if not all(k in package for k in ("history","baseline_lineup","expected_lineup")):
    teams[team]={"status":"blocked","blockers":["incomplete_game_lineup_history_package"],
      "individual_skater_index":None,"individual_goalie_index":None,"availability_delta":None}
    continue
   history=package["history"]
   if history.get("team")!=team or not history.get("date") or history["date"]>=capture.date().isoformat():
    raise ValueError("Historical team identity or cutoff violation")
   for key in ("baseline_lineup","expected_lineup"):
    lineup=package[key]
    if lineup.get("lineup_type") not in ("projected","confirmed"):
     raise ValueError("Roster membership is not a game lineup")
    if not lineup.get("source") or not lineup.get("as_of") or parse_utc(lineup["as_of"])>capture:
     raise ValueError("Lineup missing prior timestamp or source")
   result=game_report(history,package["baseline_lineup"],package["expected_lineup"],
     report["generated_at_utc"],{"game_id":gid,"home":f["home"],"away":f["away"],
                                    "scheduled_start":f["start_utc"]})
   idx=result["indices"]
   delta=result["availability_delta"]
   complete=all(idx.get(k) is not None for k in ("skater_offense","goalie_save_pct_weighted","skater_toi_minutes"))
   teams[team]={"status":"individual_evidence_observed_not_calibrated" if complete else "blocked",
      "blockers":[] if complete else ["missing_prior_player_or_goalie_observations"],
      "individual_skater_index":idx.get("skater_offense"),
      "individual_goalie_index":idx.get("goalie_save_pct_weighted"),
      "historical_toi_index":idx.get("skater_toi_minutes"),
      "availability_delta":delta,
      "lineup_confidence":result["lineup_confidence"],
      "absent_player_ids":result["absent_from_baseline"],
      "replacement_player_ids":result["replacement_player_ids"],
      "source_baseline":result["baseline_lineup_source"],
      "source_expected":result["expected_lineup_source"]}
  games.append({"game_id":gid,"home":f["home"],"away":f["away"],"teams":teams,
    "official":False,"applied_to_ml":False})
 return {"kind":"nhl_individual_player_goalie_evidence_247",
  "as_of_utc":report["generated_at_utc"],"games":games,"official_predictions":0,
  "calibrated":False,"odds_used":False,
  "limitations":["Individual prior-date indices are not full CRS or GSAx.",
    "Source-asserted projected/confirmed lineups are not independent starter confirmation.",
    "No ML/RT/+3 effect until fitted and validated."]}
def main():
 p=argparse.ArgumentParser()
 for k in ("report","packages","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 x=evaluate_fixture(json.loads(Path(a.report).read_text()),json.loads(Path(a.packages).read_text()))
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,indent=2))
 print(json.dumps({"games":len(x["games"]),"individual_evidence_teams":sum(t["status"]=="individual_evidence_observed_not_calibrated" for g in x["games"] for t in g["teams"].values()),"official_predictions":0}))
if __name__=="__main__":main()
