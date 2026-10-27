import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goal_process import calculate,goal_rates
class TestGoalProcess(unittest.TestCase):
 def team(self,gf,ga,gp=10):
  return {"crs_evidence":{"goals_for_per_game":gf,"goals_against_per_game":ga,"games_played":gp}}
 def test_symmetry(self):
  x=calculate(3.,3.)
  self.assertAlmostEqual(x["illustrative_ml"]["home"],.5,places=4)
  self.assertAlmostEqual(x["regulation"]["home"],x["regulation"]["away"],places=4)
  self.assertAlmostEqual(x["regulation"]["home"]+x["regulation"]["away"]+x["regulation"]["draw"],1,places=4)
  self.assertAlmostEqual(x["three_goal_lead"]["home"],x["three_goal_lead"]["away"],places=4)
  self.assertLessEqual(sum(x["first_to_three_goal_lead"].values()),1.00001)
  self.assertFalse(x["calibrated"])
 def test_stronger_scoring_improves_projection(self):
  a=calculate(4.,2.)
  self.assertGreater(a["illustrative_ml"]["home"],.5)
  self.assertGreater(a["three_goal_lead"]["home"],a["three_goal_lead"]["away"])
 def test_missing_team_data_rejected(self):
  with self.assertRaises(ValueError):goal_rates(self.team(3,2),{"crs_evidence":{}})
 def test_no_external_odds(self):
  h,a=goal_rates(self.team(4,3),self.team(2,4))
  self.assertGreater(h,a)
if __name__=="__main__":unittest.main()
