import unittest
from nhl.pulso_coverage_gate_225 import summarize
from nhl.pulso_evidence_coverage_222_223 import FIELDS
class Audit225(unittest.TestCase):
 def report(self,stamp):
  flags={f:False for f in FIELDS};flags["schedule"]=True;flags["roster_pool"]=True
  return {"kind":"collective_evidence_coverage","games":[{"game_id":"1","as_of":stamp,"home":"EDM","away":"COL",
   "sufficient_for_full_model":False,"teams":{t:{"coverage":flags} for t in ("EDM","COL")}}]}
 def test_empty_blocks(self):
  x=summarize([])
  self.assertEqual(x["team_observations"],0)
  self.assertFalse(x["training_gate"]["training_permitted"])
 def test_real_coverage_not_imputed(self):
  x=summarize([self.report("2026-10-29T20:00:00Z")])
  self.assertEqual(x["coverage"]["roster_pool"]["available"],2)
  self.assertEqual(x["coverage"]["goalie_confirmed"]["available"],0)
  self.assertEqual(x["verified_historical_training_rows"],0)
 def test_duplicate_daily_capture_counts_once(self):
  x=summarize([self.report("2026-10-29T20:00:00Z"),self.report("2026-10-29T21:00:00Z")])
  self.assertEqual(x["unique_fixtures"],1)
  self.assertEqual(x["team_observations"],2)
if __name__=="__main__":unittest.main()
