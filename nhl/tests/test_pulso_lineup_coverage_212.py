import unittest
from unittest.mock import patch
from nhl.pulso_lineup_coverage_212 import evaluate
class Test212(unittest.TestCase):
 def test_partial_projected_lineup_stays_blocked(self):
  stub={"game_id":"9","source_url":"https://www.nhl.com/news/example","source_captured_at":"2026-10-29T10:00:00Z",
   "teams":[{"team":t,"projected_skaters":[{"player_id":i+1,"position_group":"forward"} for i in range(5)],
   "unresolved_skaters":["Unclear Name"]} for t in ("EDM","COL")]}
  with patch("nhl.pulso_lineup_coverage_212.resolve",return_value=stub):
   result=evaluate({},[],{})
  self.assertFalse(result["projection_identity_coverage_complete"])
  self.assertFalse(result["available_for_numeric_crs"])
  self.assertIsNone(result["probabilities"])
 def test_complete_identity_still_not_confirmed(self):
  skaters=[{"player_id":i+1,"position_group":"forward" if i<12 else "defense"} for i in range(18)]
  stub={"game_id":"9","source_url":"https://www.nhl.com/news/example","source_captured_at":"2026-10-29T10:00:00Z",
  "teams":[{"team":t,"projected_skaters":skaters,"unresolved_skaters":[]} for t in ("EDM","COL")]}
  with patch("nhl.pulso_lineup_coverage_212.resolve",return_value=stub):
   result=evaluate({},[],{})
  self.assertTrue(result["projection_identity_coverage_complete"])
  self.assertFalse(result["full_team_predictions_eligible"])
if __name__=="__main__":unittest.main()
