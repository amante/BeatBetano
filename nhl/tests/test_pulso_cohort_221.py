import unittest
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_official_outcome_audit_219 import audit
class Cohort221(unittest.TestCase):
 def test_pending_cohort_does_not_score(self):
  record={"game_id":"2026020207","home":"STL","away":"BOS","start_utc":"2026-10-30T00:00:00Z",
   "prediction_as_of_utc":"2026-10-29T23:51:00Z","source_asof_utc":"2026-10-29T23:51:00Z",
   "source_url":"https://github.com/amante/BeatBetano","model_version":"outcome-only-206-frozen-params",
   "market":"ml","probabilities":{"home":0.56,"away":0.44},
   "odds_used_in_model":False,"point_in_time_sources_verified":True}
  frozen=freeze_prediction(record)
  outcome=audit([frozen],lambda _:{"id":2026020207,"gameState":"LIVE"})
  self.assertEqual(outcome["scored"],0)
  self.assertEqual(outcome["pending_games"],["2026020207"])
if __name__=="__main__":unittest.main()
