import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hybrid_gate_audit import route,audit
G=[{"season":2027,"game_id":str(i),"tipoff_utc":f"2026-10-{i+10:02d}T21:00:00Z","home_team":"BOS" if i%2 else "NYK","away_team":"NYK" if i%2 else "BOS","home_points":102+i,"away_points":100+i} for i in range(5)]
class Tests(unittest.TestCase):
 def test_current_sample_gate_unchanged(self):
  self.assertEqual(route(.6,.7,2,5,3),(.6,"sample_gate"))
 def test_challenger_eligible_after_threshold(self):
  self.assertEqual(route(.6,.7,3,4,3),(.7,"challenger"))
 def test_strong_favorite_stays_elo(self):
  self.assertEqual(route(.85,.72,10,10,0),(.85,"strong_favorite"))
 def test_evaluates_all_versions_without_approval(self):
  x=audit(G);self.assertEqual(x["seasons"]["2027"]["current_gate_3"]["n"],5)
  self.assertIn("gate_0",x["seasons"]["2027"])
  self.assertFalse(x["selection_authorized"])
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):audit(G+[G[0]])
if __name__=="__main__":unittest.main()
