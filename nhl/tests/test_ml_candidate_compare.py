import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ml_candidate_compare import comparison,markdown
class MLCompareTests(unittest.TestCase):
 def history(self):
  rows=[]
  for year in (2024,2025,2026):
   for day in range(1,21):
    rows.append({"date":f"{year}-10-{day:02d}","id":f"{year}-{day}",
     "home":"BOS","away":"MTL","hg":3+(day%2),"ag":2})
  return rows
 def test_holdout_report_is_unpromoted(self):
  x=comparison(self.history())
  self.assertEqual(x["candidate"]["n"],40)
  self.assertEqual(x["goal_only_proxy"]["n"],40)
  self.assertFalse(x["promotion_authorized"])
  self.assertFalse(x["full_pr132_model_validated"])
  self.assertIn("Calibration segments",markdown(x))
 def test_future_results_do_not_change_past_predictions(self):
  rows=self.history()
  first=comparison(rows)["predictions"][0]["candidate_ml_home"]
  for x in rows:
   if x["date"]>"2025-10-01":x["hg"],x["ag"]=1,5
  second=comparison(rows)["predictions"][0]["candidate_ml_home"]
  self.assertAlmostEqual(first,second,places=9)
if __name__=="__main__":unittest.main()
