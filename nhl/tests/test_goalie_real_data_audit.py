import unittest
from nhl.goalie_real_data_audit import audit
class RealAuditTests(unittest.TestCase):
 def test_real_source_coverage_is_not_validation(self):
  cross={"observations":[{"team":"BOS","source_captured_at":"2026-10-29T12:00:00Z",
    "nhl_game_id":"1","goalie_status":"probable","nhl_player_id":15,
    "usable_pregame_identity":True,"validation_errors":[]}]}
  history=[{"game_id":"old","date":"2026-10-28",
   "home":{"team":"BOS","players":{"15":{"goalie_games":5,"goalie_shots":150,"goalie_saves":140}}},
   "away":{"team":"MTL","players":{}}}]
  rosters=[{"team":"BOS","players":[{"player_id":15,"position_group":"goalie"}]}]
  a=audit(cross,history,rosters)
  self.assertEqual(a["summary"]["historically_rated"],1)
  self.assertFalse(a["calibrated_win_probability"])
  self.assertFalse(a["official_model_promoted"])
 def test_invalid_identity_not_scored(self):
  cross={"observations":[{"team":"BOS","source_captured_at":"2026-10-29T12:00:00Z",
    "nhl_player_id":15,"usable_pregame_identity":False,"validation_errors":["fixture_mismatch"]}]}
  a=audit(cross,[],[])
  self.assertEqual(a["summary"]["not_rated"],1)
if __name__=="__main__":unittest.main()
