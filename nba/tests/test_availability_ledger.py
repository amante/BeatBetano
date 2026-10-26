import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability_ledger import archive,join
S={"content_sha256":"digest","created_at_utc":"2026-10-26T16:00:00Z",
 "predictions":[{"game_id":"42","tipoff_utc":"2026-10-27T00:00:00Z",
 "home_team":"BOS","away_team":"NYK","hybrid_p_home":.56}]}
F={"snapshot_sha256":"digest","games":{"42":{"feature_complete":False}}}
class Test(unittest.TestCase):
 def test_freeze(self):
  a=archive(S,F)
  self.assertFalse(a["games"][0]["ready_for_fitting"])
  self.assertFalse(a["postgame_outcomes_included"])
 def test_matching_postgame_join(self):
  a=archive(S,F)
  r=join(a,{"games":[{"game_id":"42","status":"final","home_team":"BOS",
                     "away_team":"NYK","home_score":110,"away_score":105}]})
  self.assertEqual(r["joined_results"][0]["home_win"],1)
  self.assertFalse(r["authorized_to_adjust_predictions"])
 def test_detect_tampering(self):
  a=archive(S,F);a["games"][0]["baseline_p_home"]=.98
  with self.assertRaises(ValueError):join(a,{"games":[]})
 def test_no_future_prediction(self):
  s=dict(S,created_at_utc="2026-10-27T00:01:00Z")
  with self.assertRaises(ValueError):archive(s,F)
 def test_mismatch(self):
  with self.assertRaises(ValueError):archive(S,dict(F,snapshot_sha256="other"))
if __name__=="__main__":unittest.main()
