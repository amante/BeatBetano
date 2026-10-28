import unittest
from nhl.ml_robustness_control import intervals,means,loss
class RobustnessAuditTests(unittest.TestCase):
 def test_loss(self):
  self.assertAlmostEqual(loss(.6,1)[0],.16)
 def test_paired_cluster_bootstrap_reproducible(self):
  rows=[{"date":"2026-03-%02d"%i,"baseline":(.2,.5),"combined":(.15,.45)} for i in range(1,21)]
  a=intervals(rows,"baseline","combined",100)
  self.assertEqual(a,intervals(rows,"baseline","combined",100))
  self.assertLess(a["delta_brier_95pct_interval"][1],0)
 def test_metrics(self):
  x=[{"combined":(.2,.4)},{"combined":(.4,.6)}]
  self.assertEqual(means(x,"combined")["brier"],.3)
if __name__=="__main__":unittest.main()
