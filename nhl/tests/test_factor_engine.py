import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from factor_engine import process
from goal_process import calculate
class TestFactors(unittest.TestCase):
 def team(self,gf,ga,shots,against):
  return {"crs_evidence":{"games_played":10,"goals_for_per_game":gf,
    "goals_against_per_game":ga,"shots_for_per_game":shots,"shots_against_per_game":against},
    "special_teams_evidence":{"power_play_pct_observed":0.3,"penalty_kill_pct_observed":0.8}}
 def game(self):
  return {"home_team":"CAR","away_team":"BOS",
    "home_evidence":self.team(4,2,36,25),
    "away_evidence":self.team(2,4,24,35)}
 def test_factors_are_used_and_audited(self):
  a=process(self.game())
  self.assertGreater(a["home_goals_rate"],a["away_goals_rate"])
  self.assertTrue(a["factor_audit"]["shots_measured_home"])
  self.assertFalse(a["factor_audit"]["goalie_applied"])
  self.assertFalse(a["factor_audit"]["pp_pk_applied"])
  self.assertFalse(a["factor_audit"]["factor_weights_fitted"])
  self.assertGreater(calculate(a["home_goals_rate"],a["away_goals_rate"])["illustrative_ml"]["home"],0.5)
 def test_missing_shots_neutral(self):
  g=self.game();g["home_evidence"]["crs_evidence"]["shots_for_per_game"]=None
  x=process(g)
  self.assertEqual(x["factor_audit"]["shot_proxy_home_multiplier"],1)
 def test_invalid_scoring_rejected(self):
  g=self.game();g["home_evidence"]["crs_evidence"]["goals_for_per_game"]=-2
  with self.assertRaises(ValueError):process(g)
if __name__=="__main__":unittest.main()
