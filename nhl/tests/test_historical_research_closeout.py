import unittest
from nhl.historical_research_closeout import softmax,predicted,scores
class ResearchCloseoutTests(unittest.TestCase):
 def test_softmax(self):
  p=softmax([2,1,0]);self.assertAlmostEqual(sum(p),1.)
 def test_direction(self):
  cats=("home","draw","away");p=(.4,.2,.4)
  self.assertGreater(predicted(p,cats,1,.3)[0],p[0])
  self.assertLess(predicted(p,cats,1,.3)[2],p[2])
 def test_no_feature_does_not_change(self):
  p=[.48,.52];self.assertEqual(predicted(p,("home","away"),None,.4),p)
 def test_multitarget_brier(self):
  r=[{"game_id":"1","y":{"rt":"draw"},"probs":{"rt":[.4,.2,.4]}}]
  out=scores(r,"rt",{"1":{"goalie":None,"skater":None}},0.)
  self.assertEqual(out["n"],1)
  self.assertGreater(out["log_loss"],1)
if __name__=="__main__":unittest.main()
