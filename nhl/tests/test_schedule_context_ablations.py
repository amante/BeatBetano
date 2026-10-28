import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schedule_context_ablations import context,adjust,scoring

def row(d,i,h="BOS",a="MTL"):
 return {"date":d,"game_id":i,"home":h,"away":a}
class ScheduleContextTests(unittest.TestCase):
 def test_rest_uses_prior_days_only_and_rivalry(self):
  rows=[row("2025-10-01","a"),row("2025-10-03","b"),
        row("2025-10-03","c","TOR","OTT")]
  out=context(rows)
  self.assertFalse(out["a"]["rest_known"])
  self.assertEqual(out["b"]["rest"],0)
  self.assertTrue(out["b"]["division"])
  self.assertTrue(out["b"]["rivalry"])
  self.assertFalse(out["c"]["rest_known"])
 def test_no_same_day_leakage(self):
  x=[row("2025-10-01","a"),row("2025-10-01","b"),
     row("2025-10-03","c")]
  out=context(x)
  self.assertEqual(out["a"]["rest"],out["b"]["rest"])
  self.assertEqual(out["c"]["rest"],0)  # both opponents last played on Oct 1
 def test_zero_adjustment(self):
  ctx={"rest":2,"division":1,"rivalry":1}
  self.assertAlmostEqual(adjust(.63,ctx,(0.,0.,0.)),.63)
 def test_metrics(self):
  p={"game_id":"a","y":{"ml":"home"},"probs":{"ml":[.6,.4]}}
  m=scoring([p],{"a":{"rest":0,"division":0,"rivalry":0}},(0.,0.,0.))
  self.assertEqual(m["n"],1)
  self.assertAlmostEqual(m["brier"],.16)
if __name__=="__main__":unittest.main()
