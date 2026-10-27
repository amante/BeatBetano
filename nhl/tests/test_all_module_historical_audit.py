import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from all_module_historical_audit import chronological_context,audit
class HistoricalModulesTests(unittest.TestCase):
 def test_same_day_rest_does_not_leak(self):
  games=[
   {"date":"2026-03-01","id":"1","home":"BOS","away":"MTL","hg":3,"ag":2},
   {"date":"2026-03-01","id":"2","home":"BOS","away":"NYR","hg":1,"ag":2},
   {"date":"2026-03-03","id":"3","home":"BOS","away":"MTL","hg":4,"ag":1}]
  c=chronological_context(games)
  self.assertIsNone(c["1"]["home_rest_days"])
  self.assertIsNone(c["2"]["home_rest_days"])
  self.assertEqual(c["3"]["home_rest_days"],1)
  self.assertTrue(c["3"]["rivalry_registry"])
 def test_all_module_status_prevents_promotion(self):
  games=[{"date":"2026-03-01","id":"1","home":"BOS","away":"MTL","hg":3,"ag":2}]
  r=audit(games)
  self.assertEqual(len(r["module_status"]),14)
  self.assertFalse(r["model_promotion_authorized"])
  self.assertFalse(r["module_status"]["goalie_daily"]["validated_effect"])
  self.assertEqual(r["module_status"]["context"]["status"],"partial_observed_not_fitted")
if __name__=="__main__":unittest.main()
