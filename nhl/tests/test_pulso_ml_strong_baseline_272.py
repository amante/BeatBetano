import unittest
from datetime import date,timedelta
from nhl.pulso_ml_strong_baseline_272 import evaluate
from nhl.tests.test_pulso_goalie_model_269 import GoalieModel269
def sample():
 report=GoalieModel269().sample()
 labels=[{"game_id":str(i+10000),"date":(date(2023,1,1)+timedelta(days=i//10)).isoformat(),
          "home":"X","away":"Y","ml_winner":"home" if i%2 else "away"} for i in range(2211)]
 labels += [{k:r[k] for k in ("game_id","date","home","away","ml_winner")} for r in report["eligible_rows"]]
 return report,labels
class StrongBaseline272(unittest.TestCase):
 def test_identical_test_and_frozen_baseline(self):
  r=evaluate(*sample())
  self.assertEqual(r["holdout_n"],120)
  self.assertEqual(r["teams_only_calibrated"]["n"],r["frozen_218"]["n"])
  self.assertEqual(sum(b["n"] for b in r["calibration_bins"]),120)
  self.assertFalse(r["production_approved"])
 def test_label_mismatch_is_rejected(self):
  a,b=sample();b[-1]["ml_winner"]="away" if b[-1]["ml_winner"]=="home" else "home"
  with self.assertRaises(ValueError):evaluate(a,b)
 def test_prior_date_gate(self):
  a,b=sample();a["eligible_rows"][0]["feature_as_of_date"]=a["eligible_rows"][0]["date"]
  with self.assertRaises(ValueError):evaluate(a,b)
if __name__=="__main__":unittest.main()
