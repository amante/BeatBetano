import unittest
from nhl.pulso_goalie_ablation_270 import assess,GROUPS
from nhl.tests.test_pulso_goalie_model_269 import GoalieModel269
class Ablation270(unittest.TestCase):
 def test_four_comparable_groups(self):
  r=assess(GoalieModel269().sample())
  self.assertEqual(set(r["groups"]),set(GROUPS))
  self.assertEqual({v["holdout"]["n"] for v in r["groups"].values()},{r["holdout_n"]})
  self.assertFalse(r["automatic_promotion"])
 def test_prior_date_gate(self):
  d=GoalieModel269().sample();d["eligible_rows"][1]["feature_as_of_date"]=d["eligible_rows"][1]["date"]
  with self.assertRaises(ValueError):assess(d)
if __name__=="__main__":unittest.main()
