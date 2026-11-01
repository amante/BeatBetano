import unittest
from nhl.pulso_ml_decision_271 import gate
def report():
 return {"kind":"nhl_goalie_ablation_270","odds_used":False,"holdout_n":524,
         "groups":{name:{"holdout":{"n":524,"brier":b,"log_loss":l}} for name,b,l in
         (("constant",.249093,.691340),("teams",.245917,.684955),
          ("goalies",.249110,.691368),("combined",.245972,.685059))}}
class Decision271(unittest.TestCase):
 def test_real_rounded_metrics_block_goalies(self):
  r=gate(report())
  self.assertEqual(r["research_candidate"],"teams_only")
  self.assertEqual(r["goalie_conditioning_status"],"blocked_no_incremental_value")
  self.assertFalse(r["production_approved"])
 def test_missing_market_fails_closed(self):
  r=report();del r["groups"]["goalies"]
  with self.assertRaises(ValueError):gate(r)
 def test_no_odds(self):
  r=report();r["odds_used"]=True
  with self.assertRaises(ValueError):gate(r)
 def test_mismatched_holdout_rejected(self):
  r=report();r["groups"]["teams"]["holdout"]["n"]=100
  with self.assertRaises(ValueError):gate(r)
 def test_even_success_does_not_auto_promote(self):
  r=report();r["groups"]["combined"]["holdout"].update(brier=.22,log_loss=.65)
  self.assertFalse(gate(r)["production_approved"])
if __name__=="__main__":unittest.main()
