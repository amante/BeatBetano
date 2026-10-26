import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_team_stats import collect
URL="https://api-web.nhle.com/v1/standings/2026-10-25"
class Tests(unittest.TestCase):
 def test_features_no_fitted_impact(self):
  r=collect({"standings":[{"teamAbbrev":{"default":"BOS"},"gamesPlayed":4,
   "goalFor":14,"goalAgainst":10,"powerPlayPct":21.4,"penaltyKillPct":80}]},URL,"2026-10-26T12:00:00Z")["BOS"]
  self.assertAlmostEqual(r["goal_diff_per_game_shrunk"],4/14)
  self.assertEqual(r["power_play_pct_observed"],21.4)
  self.assertIsNone(r["sustainable_special_teams_strength"])
  self.assertIsNone(r["crs"])
 def test_partial_missing_is_not_zero(self):
  r=collect({"standings":[{"teamAbbrev":{"default":"BOS"},"gamesPlayed":4}]},URL,"2026-10-26T12:00:00Z")["BOS"]
  self.assertIsNone(r["power_play_pct_observed"])
 def test_nonofficial_source_rejected(self):
  with self.assertRaises(ValueError):collect({}, "https://example.com","2026-10-26T12:00:00Z")
if __name__=="__main__":unittest.main()
