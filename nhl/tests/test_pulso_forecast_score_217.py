import unittest
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_forecast_score_217 import evaluate
class Tests(unittest.TestCase):
 def forecast(self):
  r={"game_id":"1","home":"EDM","away":"COL","start_utc":"2026-10-30T23:00:00Z",
   "prediction_as_of_utc":"2026-10-30T20:00:00Z","source_asof_utc":"2026-10-30T19:00:00Z",
   "source_url":"https://www.nhl.com","model_version":"research-1","market":"ml",
   "probabilities":{"home":.6,"away":.4},"odds_used_in_model":False,
   "point_in_time_sources_verified":True}
  return freeze_prediction(r)
 def label(self):
  return {"game_id":"1","home":"EDM","away":"COL","ml_winner":"home","rt_result":"home",
   "first_to_plus3":"home","home_reached_plus3":"True","away_reached_plus3":"False"}
 def test_real_frozen_score(self):
  x=evaluate([self.forecast()],[self.label()])
  self.assertEqual(x["scored"],1)
  self.assertEqual(x["metrics"][0]["brier"],.16)
  self.assertFalse(x["official_promotion"])
 def test_source_only_never_scores(self):
  with self.assertRaises(ValueError):evaluate([{"payload":{"run_id":"1"}}],[self.label()])
 def test_tampering_detected(self):
  x=self.forecast();x["record"]["probabilities"]={"home":.7,"away":.3}
  with self.assertRaisesRegex(ValueError,"integrity"):evaluate([x],[self.label()])
 def test_duplicates_rejected(self):
  x=self.forecast()
  with self.assertRaisesRegex(ValueError,"Multiple"):evaluate([x,x],[self.label()])
 def test_pending(self):
  r=evaluate([self.forecast()],[])
  self.assertEqual(r["scored"],0);self.assertEqual(len(r["pending"]),1)
if __name__=="__main__":unittest.main()
