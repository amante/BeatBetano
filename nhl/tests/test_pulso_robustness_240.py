import unittest
from nhl.pulso_robustness_240 import quantify
class Robustness240(unittest.TestCase):
 def setUp(self):
  self.labels=[{"game_id":str(i),"date":"2026-03-%02d"%(i+1),"home":"BOS","away":"MTL",
   "ml_winner":"home" if i%2 else "away"} for i in range(12)]
  self.challenger={"status":"research_only_challenger_fitted","promoted":False,
   "holdout_start":"2026-03-01","holdout_games":12,
   "holdout_predictions":[{"game_id":str(i),"date":"2026-03-%02d"%(i+1),
    "p_home_ml":.65 if i%2 else .35,"actual_home_ml":1 if i%2 else 0} for i in range(12)]}
 def test_reproducible_date_bootstrap(self):
  a=quantify(self.challenger,self.labels,iterations=200,seed=3)
  c=quantify(self.challenger,self.labels,iterations=200,seed=3)
  self.assertEqual(a["uncertainty"],c["uncertainty"])
  self.assertEqual(a["paired_games"],12)
  self.assertFalse(a["decision"]["challenger_promotion_allowed"])
 def test_mismatched_outcome_rejected(self):
  self.challenger["holdout_predictions"][0]["actual_home_ml"]=1
  with self.assertRaises(ValueError):quantify(self.challenger,self.labels,iterations=200)
 def test_duplicate_rejected(self):
  self.challenger["holdout_predictions"][0]["game_id"]="1"
  with self.assertRaises(ValueError):quantify(self.challenger,self.labels,iterations=200)
 def test_low_bootstrap_count_rejected(self):
  with self.assertRaises(ValueError):quantify(self.challenger,self.labels,iterations=5)
 def test_missing_dates_rejected(self):
  self.challenger["holdout_start"]="2026-03-30"
  with self.assertRaises(ValueError):quantify(self.challenger,self.labels,iterations=200)
if __name__=="__main__":unittest.main()
