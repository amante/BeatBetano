import unittest
from nhl.pulso_collective_audit_208 import audit,freeze_prediction
class Tests(unittest.TestCase):
 def test_paired_bootstrap_zero_when_models_equal(self):
  rows=[{"y":{"ml":"home"},"probs":{"ml":[.7,.3]},"baseline_probs":{"ml":[.7,.3]}} for _ in range(5)]
  from unittest.mock import patch
  with patch("nhl.pulso_collective_audit_208.CATEGORIES",{"ml":("home","away")}):
   r=audit(rows,bootstrap=30)
  self.assertEqual(r["markets"]["ml"]["uncertainty"]["brier"]["ci95"],[0.,0.])
 def test_ledger_rejects_late(self):
  p={"game_id":"1","start_utc":"2026-10-30T00:00:00Z","prediction_as_of_utc":"2026-10-30T00:00:00Z",
   "source_asof_utc":"2026-10-29T22:00:00Z","source_url":"https://nhl.com",
   "model_version":"test","market":"ml","probabilities":{"home":.5,"away":.5},
   "odds_used_in_model":False,"point_in_time_sources_verified":True}
  with self.assertRaises(ValueError):freeze_prediction(p)
  p["prediction_as_of_utc"]="2026-10-29T23:00:00Z"
  self.assertTrue(freeze_prediction(p)["frozen"])
  p["probabilities"]={"home":.6,"away":.5}
  with self.assertRaises(ValueError):freeze_prediction(p)
if __name__=="__main__":unittest.main()
