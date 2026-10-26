"""NHL goalie impact: matched-team, chronological OUT-OF-SAMPLE evaluation.

Input requires pregame predictions already frozen before tip and individually
verified goalie identifiers/observations. No retrospective goalie assignment
or invented matchups. This audit never auto-promotes a candidate.
"""
import argparse,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

def utc(s):
 d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timezone required")
 return d.astimezone(timezone.utc)

def evaluate(rows,min_pair_games=12):
 if not isinstance(rows,list) or not rows:raise ValueError("Historical observations required")
 seen=set();groups=defaultdict(list)
 for r in rows:
  gid=str(r["event_id"]);side=r["team"]
  key=(gid,side)
  if key in seen:raise ValueError("Duplicate game/team")
  seen.add(key)
  if r.get("sport")!="nhl" or r.get("market")!="moneyline":raise ValueError("NHL ML only")
  freeze=utc(r["prediction_as_of_utc"]);tip=utc(r["tipoff_utc"])
  obs=utc(r["goalie_observed_at_utc"]);cutoff=utc(r["training_cutoff_utc"])
  if not (cutoff<freeze<tip and obs<=freeze):raise ValueError("Future information leaked")
  if r.get("goalie_confirmed_at_freeze") is not True:raise ValueError("Unverified starting goalie")
  if r.get("sources_verified") is not True or r.get("bookmaker_odds_used") is not False:
   raise ValueError("Unverified/market-anchored record")
  p=r.get("baseline_win_probability");y=r.get("team_won")
  if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1 or type(y) is not int or y not in (0,1):
   raise ValueError("Invalid probability/outcome")
  goalie=r.get("goalie_id");team=r.get("team")
  if not goalie or not team or not r.get("season_end_year"):raise ValueError("Missing lineage")
  groups[(team,int(r["season_end_year"]))].append(r)
 report=[]
 for (team,year),games in sorted(groups.items()):
  bygoalie=defaultdict(list)
  for g in games:bygoalie[str(g["goalie_id"])].append(g)
  for goalie,games_a in sorted(bygoalie.items()):
   others=[g for g in games if str(g["goalie_id"])!=goalie]
   if len(games_a)<min_pair_games or len(others)<min_pair_games:continue
   def residual(xs):return sum(g["team_won"]-g["baseline_win_probability"] for g in xs)/len(xs)
   def brier(xs):return sum((g["baseline_win_probability"]-g["team_won"])**2 for g in xs)/len(xs)
   report.append({"team":team,"season_end_year":year,"goalie_id":goalie,
     "games_with":len(games_a),"games_without":len(others),
     "with_goalie_residual":residual(games_a),"without_goalie_residual":residual(others),
     "residual_difference":residual(games_a)-residual(others),
     "with_goalie_brier":brier(games_a),"without_goalie_brier":brier(others),
     "causal_effect_claimed":False,
     "confounders_not_resolved":["opponent_quality","defense_deployment","rest","injuries"]})
 return {"sport":"nhl","market":"moneyline","matched_team_season_goalie_diagnostics":report,
  "records":len(rows),"independently_validated":False,"promote_to_official":False,
  "calibrated_goalie_rating":None,
  "note":"Observational association, not causal goalie effect. Team/opponent/time confounding remains; a true walk-forward challenger must be fitted and scored prospectively."}

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True)
 p.add_argument("--min-pair-games",type=int,default=12);a=p.parse_args()
 if a.min_pair_games<1:raise ValueError("Positive minimum required")
 out=evaluate(json.loads(Path(a.input).read_text()),a.min_pair_games)
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(out,indent=2));print(json.dumps({"diagnostics":len(out["matched_team_season_goalie_diagnostics"]),"validated":False}))
if __name__=="__main__":main()
