import unittest
from nhl.pulso_prospective_reconcile_216 import reconcile
class Test216(unittest.TestCase):
 def entry(self):
  return {"payload":{"run_id":"42","source_report":{"generated_at_utc":"2026-10-29T12:00:00Z",
   "games":[{"game_id":"7","home":"EDM","away":"COL","start_utc":"2026-10-29T23:00:00Z",
     "official":False,"probabilities":None}]}}}
 def test_join_outcome_without_scoring(self):
  labels=[{"game_id":"7","home":"EDM","away":"COL","ml_winner":"home","rt_result":"draw",
   "first_to_plus3":"None","home_reached_plus3":"False","away_reached_plus3":"False"}]
  result=reconcile([self.entry()],labels)
  self.assertEqual(result["by_state"]["completed_source_only_no_prediction"],1)
  self.assertFalse(result["rows"][0]["scored"])
  self.assertIsNone(result["metrics"])
 def test_unfinished_is_not_winner(self):
  self.assertEqual(reconcile([self.entry()],[])["by_state"]["awaiting_official_result"],1)
 def test_late_capture_is_rejected(self):
  x=self.entry();x["payload"]["source_report"]["games"][0]["start_utc"]="2026-10-29T11:00:00Z"
  with self.assertRaises(ValueError):reconcile([x],[])
 def test_false_forecast_is_rejected(self):
  x=self.entry();x["payload"]["source_report"]["games"][0]["probabilities"]={"home":.6,"away":.4}
  with self.assertRaises(ValueError):reconcile([x],[])
if __name__=="__main__":unittest.main()
