import unittest
from nhl.goalie_team_walkforward_184 import history_signal,score
class WalkForwardTests(unittest.TestCase):
 def test_prior_goalie_signal(self):
  row={"home":{"players":{"1":{"role":"goalie","goalie_games":5,"goalie_saves":90,"goalie_shots":100}}},
       "away":{"players":{}}}
  self.assertAlmostEqual(history_signal(row,"home"),180.5/200)
  self.assertIsNone(history_signal(row,"away"))
 def test_baseline_identical_with_zero_coef(self):
  data=[{"base":.65,"signal":.1,"y":1},{"base":.4,"signal":None,"y":0}]
  result=score(data,0.)
  self.assertAlmostEqual(result["brier"],(.35**2+.4**2)/2,places=6)
  self.assertEqual(result["coverage"],1)
  self.assertEqual(sum(x["n"] for x in result["calibration_bins"]),2)
if __name__=="__main__":unittest.main()
