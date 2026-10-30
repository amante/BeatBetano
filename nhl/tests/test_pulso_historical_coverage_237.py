import unittest
from nhl.pulso_historical_coverage_237 import audit
class Audit237(unittest.TestCase):
 def setUp(self):
  f={"past_games":6,"prior_goalie_save_pct":0.91,"prior_skater_goals_per_observed_game":3.0}
  self.rows=[{"game_id":"2025020001","date":"2025-10-01","home":"BOS","away":"MTL",
   "features":{"home":f.copy(),"away":f.copy()},"target":{"ml_winner":"home"}}]
 def test_complete(self):
  result=audit(self.rows)
  self.assertEqual(result["eligible_games"],1)
  self.assertEqual(result["core_counts"]["home_prior_goalie_save_pct"],1)
 def test_missing(self):
  self.rows[0]["features"]["home"]["prior_goalie_save_pct"]=None
  self.assertEqual(audit(self.rows)["eligible_games"],0)
 def test_thin(self):
  self.rows[0]["features"]["away"]["past_games"]=2
  self.assertEqual(audit(self.rows)["eligible_games"],0)
 def test_duplicate(self):
  with self.assertRaises(ValueError):audit(self.rows*2)
 def test_leakage(self):
  self.rows[0]["features"]["away"]["ml_winner"]="away"
  with self.assertRaises(ValueError):audit(self.rows)
 def test_invalid_sv(self):
  self.rows[0]["features"]["home"]["prior_goalie_save_pct"]=1.4
  with self.assertRaises(ValueError):audit(self.rows)
if __name__=="__main__":unittest.main()
