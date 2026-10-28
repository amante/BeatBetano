"""Game-specific NHL expected lineup versus independently sourced baseline.

Quantitative offense, historic TOI, and goalie SV% evidence only. Candidate
roster membership cannot serve as expected lineup. No bookmaker odds or
probability predictions. Missing evidence prevents numeric delta.
"""
import argparse,json
from pathlib import Path
try:
 from nhl.individual_roster_indices import evaluate
 from nhl.roster_source_adapter import adapt
except ModuleNotFoundError:
 from individual_roster_indices import evaluate
 from roster_source_adapter import adapt

def game_report(history,baseline,expected,prediction_time,fixture):
 if not fixture.get("game_id") or not fixture.get("home") or not fixture.get("away"):
  raise ValueError("Game identifier and competing teams required")
 team=history["team"]
 if team not in (fixture["home"],fixture["away"]) or fixture["home"]==fixture["away"]:
  raise ValueError("Lineup team not in matchup")
 if not fixture.get("scheduled_start"):raise ValueError("Game start required")
 from datetime import timezone
 try:
  from nhl.roster_aware_units import timepoint
 except ModuleNotFoundError:
  from roster_aware_units import timepoint
 if timepoint(prediction_time)>timepoint(fixture["scheduled_start"]):
  raise ValueError("Prediction is not pregame")
 if baseline.get("lineup_type") not in ("projected","confirmed") or expected.get("lineup_type") not in ("projected","confirmed"):
  raise ValueError("Candidate rosters are not a game-specific lineup")
 base=adapt(baseline,team,prediction_time)
 current=adapt(expected,team,prediction_time)
 index=evaluate(history,baseline,expected,prediction_time)
 def deployed(lineup):
  return {p["player_id"]:p for p in lineup["players"] if p["status"]!="out" and p["expected_share"]>0}
 b=deployed(base);e=deployed(current)
 absences=sorted(set(b)-set(e));replacements=sorted(set(e)-set(b))
 role_changes=[{"player_id":i,"from":b[i]["unit"],"to":e[i]["unit"],
                 "baseline_share":b[i]["expected_share"],"expected_share":e[i]["expected_share"]}
              for i in sorted(set(b)&set(e))
              if b[i]["unit"]!=e[i]["unit"] or b[i]["expected_share"]!=e[i]["expected_share"]]
 for p in current["players"]:
  if p["status"]=="confirmed" and expected["lineup_type"]!="confirmed":
   raise ValueError("Unverified player confirmation")
 out_players=sorted(p["player_id"] for p in current["players"] if p["status"]=="out")
 if expected["lineup_type"]=="confirmed":
  # A third-party label alone is not independently verified: retain provenance.
  confidence="source_asserted_confirmed_not_independently_verified"
 else:confidence="source_projected"
 return {"fixture":fixture,"team":team,"prediction_time":prediction_time,
  "expected_lineup_source":current["source"],"baseline_lineup_source":base["source"],
  "lineup_confidence":confidence,"absent_from_baseline":absences,
  "replacement_player_ids":replacements,"reported_out_player_ids":out_players,
  "deployment_changes":role_changes,"indices":index["expected"]["indices"],
  "availability_delta":index["availability_delta"],
  "missing_expected_history":index["expected"]["missing"],
  "missing_baseline_history":index["baseline"]["missing"],
  "full_crs":None,"full_availability_delta":None,
  "limitations":["Source-reported lineup status is not independently confirmed by this engine.",
    "Goalie index uses past save rates, not starter confirmation, opponent-adjusted GSAx or causality.",
    "Historical TOI proxy is not a forecast of actual minutes.",
    "Numerical indices are not calibrated goals or ML/RT/+3 probabilities."],
  "odds_used":False,"model_promoted":False}

def main():
 p=argparse.ArgumentParser()
 for x in ("history","baseline","expected","fixture","prediction-time","output"):
  p.add_argument("--"+x,required=True)
 a=p.parse_args()
 result=game_report(json.loads(Path(a.history).read_text()),
   json.loads(Path(a.baseline).read_text()),json.loads(Path(a.expected).read_text()),
   a.prediction_time,json.loads(Path(a.fixture).read_text()))
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2))
 print(json.dumps({"team":result["team"],"replacements":result["replacement_player_ids"],
                    "absences":result["absent_from_baseline"],
                    "deltas":result["availability_delta"]},indent=2))
if __name__=="__main__":main()
