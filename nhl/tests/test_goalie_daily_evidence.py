import unittest
from nhl.goalie_daily_evidence import assess
class GoalieDailyEvidenceTests(unittest.TestCase):
 def test_previous_date_only_and_backup(self):
  cross={"observations":[{"team":"BOS","source_captured_at":"2026-10-29T15:00:00Z","nhl_game_id":"g1",
   "goalie_status":"probable","nhl_player_id":11,"usable_pregame_identity":True,"validation_errors":[]}]}
  history=[{"game_id":"g0","date":"2026-10-28","home":{"team":"BOS","players":{"11":{"goalie_games":5,"goalie_shots":150,"goalie_saves":138},
    "12":{"goalie_games":5,"goalie_shots":100,"goalie_saves":90}}},"away":{"team":"MTL","players":{}}},
   {"game_id":"g1","date":"2026-10-29","home":{"team":"BOS","players":{"11":{"goalie_games":6,"goalie_shots":200,"goalie_saves":190}}},"away":{"team":"MTL","players":{}}}]
  rosters=[{"team":"BOS","players":[{"player_id":11,"position_group":"goalie"},{"player_id":12,"position_group":"goalie"}]}]
  r=assess(cross,history,rosters)
  self.assertEqual(r["rated"],1)
  self.assertEqual(r["goalies"][0]["historical_goalie_rating"]["shots"],150)
  self.assertIsNotNone(r["goalies"][0]["comparison"][0]["delta_shrunk_save_pct"])
  self.assertIsNone(r["goalies"][0]["goalie_daily_rating_official"])
 def test_invalid_identity_has_no_rating(self):
  cross={"observations":[{"team":"BOS","source_captured_at":"2026-10-29T15:00:00Z",
   "nhl_player_id":11,"usable_pregame_identity":False,"validation_errors":["fixture_mismatch"]}]}
  r=assess(cross,[],[])
  self.assertEqual(r["rated"],0)
  self.assertIsNone(r["goalies"][0]["historical_goalie_rating"])
if __name__=="__main__":unittest.main()
