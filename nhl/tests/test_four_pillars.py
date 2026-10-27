import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from four_pillars import team_form,teams_special,goalie_rows,build,summary

class Tests(unittest.TestCase):
 def test_no_roster_rating_from_team_form(self):
  x=team_form({"gamesPlayed":10,"goalDifferential":8,"goals_for_per_game":3.4})
  self.assertEqual(x["goal_differential_per_game"],.8)
  self.assertIsNone(x["crs"])
 def test_pp_pk_no_fake_bayesian_value(self):
  x=teams_special({"power_play_pct_observed":28,"penalty_kill_pct_observed":85})
  self.assertEqual(x["pp_percent"],28)
  self.assertIsNone(x["bayesian_pp_strength"])
 def test_candidate_uncertainty_not_starter(self):
  x=goalie_rows({"home":{"goalie_candidates":[{"goalie_id":"99","shots_against":50,"saves":45,"sample_games":2,"starts_last_7_days":1}]}},"home")
  self.assertLess(x["candidates"][0]["sv_95pct_wilson_interval"][0],.9)
  self.assertFalse(x["starter_confirmed"])
  self.assertIsNone(x["goalie_daily_rating"])
 def test_freeze_and_gate(self):
  slate={"sport":"nhl","as_of_utc":"2026-10-27T10:00:00Z","events":[{"event_id":"1","home_team":"BOS","away_team":"MTL","official_team_stats":{}}]}
  goalies={"sport":"nhl","as_of_utc":slate["as_of_utc"],"games":{}}
  x=build(slate,goalies)
  self.assertFalse(x["games"][0]["eligible_for_bet"])
  self.assertIn("BOS",summary(x))
  goalies["as_of_utc"]="2026-10-28T10:00:00Z"
  with self.assertRaises(ValueError):build(slate,goalies)
if __name__=="__main__":unittest.main()
