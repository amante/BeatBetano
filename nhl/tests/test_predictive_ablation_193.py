import unittest
from nhl.predictive_ablation_193 import VARIANTS,fit_variant
class PredictiveAblation193Tests(unittest.TestCase):
 def test_baseline_never_adjusts(self):
  self.assertEqual(fit_variant([{"features":(1.,0.,0.,0.),"actual":1,"baseline_logit":0.}],()),[0.]*4)
 def test_inactive_coefficients_are_exactly_zero(self):
  rows=[{"features":(1.,1.,i%2,0.),"baseline_logit":0.,"actual":i%2} for i in range(60)]
  w=fit_variant(rows,(2,))
  self.assertEqual(w[1],0.)
  self.assertEqual(w[3],0.)
 def test_all_ablations_declared(self):
  self.assertEqual(len(VARIANTS),8)
  self.assertEqual(VARIANTS["all_three"],(1,2,3))
if __name__=="__main__":unittest.main()
