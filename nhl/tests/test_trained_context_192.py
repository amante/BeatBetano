import unittest
from nhl.trained_context_192 import fitted_coefficients,scores,calibration,evaluate,sigmoid

class TrainedContext192Tests(unittest.TestCase):
 def test_fits_signal_not_fixed_grid(self):
  rows=[]
  for i in range(120):
   x=(1.,float((i%5)-2)/2.,0.,0.)
   rows.append({"features":x,"baseline_logit":0.,"actual":int(x[1]>0)})
  coef=fitted_coefficients(rows)
  self.assertGreater(coef[1],0.01)
  self.assertEqual(coef[2],0.)
 def test_metrics_perfect(self):
  rows=[{"actual":1,"p":1.},{"actual":0,"p":0.}]
  self.assertEqual(scores(rows,"p")["brier"],0.)
  self.assertEqual(sum(b["n"] for b in calibration(rows,"p")),2)
 def test_same_day_outcome_not_trainable(self):
  rows=[]
  for i in range(502):
   day="2025-01-%02d"%(i%28+1) if i<1 else None
   from datetime import date,timedelta
   day=(date(2024,1,1)+timedelta(days=i)).isoformat()
   rows.append({"game_id":str(i),"date":day,"home":"BOS","away":"TOR",
                "ml_winner":"home" if i%2 else "away",
                "rt_result":"home" if i%2 else "away",
                "home_reached_plus3":"True","away_reached_plus3":"False",
                "first_to_plus3":"home"})
  result=evaluate(rows,start="2025-05-01",min_train=500)
  self.assertEqual(result["test_n"],2)
  self.assertFalse(result["independent_prospective_validation"])
  self.assertIsNone(result["pp_pk_and_roster_coefficients"])
if __name__=="__main__": unittest.main()
