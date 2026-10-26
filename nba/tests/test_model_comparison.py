import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_comparison import audit,markdown
def fixture(route="challenger",hybrid=.55):
 return {"sport":"nba","games":[{"game_id":"1","away_team":"BOS","home_team":"NYK",
   "official_elo_home":.50,"challenger_home":.55,"statistical_baseline_home":hybrid,
   "hybrid_route":route,"integrated_home":None}]}
class Tests(unittest.TestCase):
 def test_three_models_and_delta(self):
  r=audit(fixture());g=r["games"][0]
  self.assertEqual(g["delta_challenger_vs_elo_pp"],5)
  self.assertEqual(g["hybrid_route"],"challenger")
  self.assertIn("Challenger local",markdown(r))
 def test_elo_fallback(self):
  r=audit(fixture("strong_favorite",.5))
  self.assertEqual(r["games"][0]["delta_hybrid_vs_elo_pp"],0)
 def test_hybrid_route_must_be_coherent(self):
  with self.assertRaisesRegex(ValueError,"route"):audit(fixture("strong_favorite",.55))
 def test_non_nba_rejected(self):
  with self.assertRaises(ValueError):audit({"sport":"nhl","games":[]})
if __name__=="__main__":unittest.main()
