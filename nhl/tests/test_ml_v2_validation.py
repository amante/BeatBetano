import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ml_v2_validation import features,probability,evaluate
from module_validation_readiness import report
class TestMLV2(unittest.TestCase):
 def test_no_same_day_leakage(self):
  original=[{"date":"2025-10-01","id":"1","home":"BOS","away":"MTL","hg":3,"ag":1},
            {"date":"2025-10-01","id":"2","home":"BOS","away":"MTL","hg":1,"ag":4},
            {"date":"2025-10-02","id":"3","home":"BOS","away":"MTL","hg":2,"ag":3}]
  a=features(original)
  self.assertEqual(a[0]["home"],[0,0,0])
  self.assertEqual(a[1]["home"],[0,0,0])
  self.assertEqual(a[2]["home"],[4,5,2])
  altered=[dict(x) for x in original];altered[1]["hg"]=8
  b=features(altered)
  self.assertEqual(probability(a[0],3,0,5),probability(b[0],3,0,5))
 def test_season_reset(self):
  rows=[{"date":"2025-04-01","id":"1","home":"BOS","away":"MTL","hg":3,"ag":1},
        {"date":"2025-10-01","id":"2","home":"BOS","away":"MTL","hg":1,"ag":2}]
  self.assertEqual(features(rows)[1]["home"],[0,0,0])
 def test_module_gate(self):
  r=report()
  self.assertTrue(r["do_not_promote"])
  self.assertFalse(r["module_validation"]["goalie_daily"]["historically_validatable"])
  self.assertFalse(r["module_validation"]["three_goal_lead"]["historically_validatable"])
if __name__=="__main__":unittest.main()
