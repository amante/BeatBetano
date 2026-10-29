import unittest
from nhl.integrated_ablation_audit_186 import evaluate,make_prediction
class IntegratedAblationTests(unittest.TestCase):
 def test_no_fake_crs_or_special_teams(self):
  # Archive count and chronological split are enforced before scoring.
  with self.assertRaises(ValueError):evaluate([])
 def test_ml_is_only_modified_target(self):
  row={"game_id":"1","date":"2026-01-01","probs":{"ml":[.55,.45],"rt":[.4,.3,.3],"first3":[.3,.3,.4],"home3":[.2,.8],"away3":[.3,.7]}}
  prediction=make_prediction(row,{"rest":1,"division":1,"rivalry":0},(.06,0,0))
  self.assertGreater(prediction["probs"]["ml"][0],.55)
  self.assertAlmostEqual(sum(prediction["probs"]["ml"]),1)
  for name in ("rt","first3","home3","away3"):self.assertEqual(prediction["probs"][name],row["probs"][name])
if __name__=="__main__":unittest.main()
