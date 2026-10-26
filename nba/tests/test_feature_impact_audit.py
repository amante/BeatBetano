import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_impact_audit import audit
from challenger import predict_challenger
G=[{"season":2027,"game_id":str(i),"tipoff_utc":f"2026-10-{i+10:02d}T22:00:00Z",
"home_team":"BOS" if i%2 else "NYK","away_team":"NYK" if i%2 else "BOS",
"home_points":102+i,"away_points":96+i} for i in range(4)]
class Tests(unittest.TestCase):
 def test_ablation_scores_all_models(self):
  x=audit(G);m=x["seasons"]["2027"]["models"]
  self.assertEqual(set(m),{"elo","challenger","hybrid","margin_only","rest_only"})
  self.assertEqual(m["challenger"]["n"],4)
  self.assertFalse(x["production_approved"])
 def test_default_challenger_unchanged(self):
  self.assertEqual(predict_challenger(G),predict_challenger(G,use_margin=True,use_rest=True))
 def test_no_duplicate_ids(self):
  with self.assertRaisesRegex(ValueError,"Duplicate"):audit(G+[G[0]])
 def test_no_history(self):
  with self.assertRaises(ValueError):audit([])
if __name__=="__main__":unittest.main()
