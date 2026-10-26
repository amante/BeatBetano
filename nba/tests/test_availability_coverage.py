import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability_ledger import archive
from availability_coverage import audit
S={"content_sha256":"x","created_at_utc":"2026-10-26T15:00:00Z","predictions":[{"game_id":"123","tipoff_utc":"2026-10-27T00:00:00Z","home_team":"BOS","away_team":"NYK","hybrid_p_home":.55}]}
def doc(full=False):
 v={"feature_complete":full}
 if full:v.update(home_features={"verified_starters":5},away_features={"verified_starters":5})
 return archive(S,{"snapshot_sha256":"x","games":{"123":v}})
class Tests(unittest.TestCase):
 def test_missing_is_visible(self):
  o=audit([doc()])
  self.assertEqual(o["games"],1);self.assertEqual(o["complete_pregame_features"],0)
  self.assertFalse(o["independent_calibration_passed"])
 def test_complete_feature_captured(self):
  o=audit([doc(True)])
  self.assertEqual(o["coverage"],1)
  self.assertEqual(o["training_rows_authorized"],0)
 def test_tampering(self):
  d=doc();d["games"][0]["feature_complete"]=True
  with self.assertRaises(ValueError):audit([d])
 def test_cross_archive_duplicate(self):
  with self.assertRaises(ValueError):audit([doc(),doc()])
if __name__=="__main__":unittest.main()
