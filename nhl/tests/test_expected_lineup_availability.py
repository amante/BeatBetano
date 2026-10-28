import unittest
from nhl.expected_lineup_availability import game_report
class ExpectedLineupTests(unittest.TestCase):
 def setUp(self):
  self.h={"team":"BOS","players":{"11":{"role":"skater","skater_games":5,"skater_goals":2,"skater_shots":15,"toi_games":5,"toi_seconds":6000},
    "12":{"role":"skater","skater_games":5,"skater_goals":1,"skater_shots":10,"toi_games":5,"toi_seconds":4500},
    "13":{"role":"goalie","goalie_games":5,"goalie_saves":130,"goalie_shots":145}}}
  self.b={"team":"BOS","source_url":"https://example.org/baseline","as_of":"2026-10-27T12:00:00Z","lineup_type":"projected",
    "players":[{"player_id":11,"unit":"top6","status":"projected","expected_share":1.},
               {"player_id":13,"unit":"goalie","status":"projected","expected_share":1.}]}
  self.e={"team":"BOS","source_url":"https://example.org/pregame","as_of":"2026-10-28T12:00:00Z","lineup_type":"projected",
    "players":[{"player_id":12,"unit":"top6","status":"projected","expected_share":1.},
               {"player_id":13,"unit":"goalie","status":"projected","expected_share":1.}]}
  self.fixture={"game_id":"test","home":"BOS","away":"MTL","scheduled_start":"2026-10-28T23:00:00Z"}
 def test_replacement_and_numeric_delta(self):
  x=game_report(self.h,self.b,self.e,"2026-10-28T19:00:00Z",self.fixture)
  self.assertEqual(x["absent_from_baseline"],[11])
  self.assertEqual(x["replacement_player_ids"],[12])
  self.assertAlmostEqual(x["availability_delta"]["skater_offense"],-.25)
  self.assertIsNone(x["full_crs"])
 def test_reject_postgame_prediction(self):
  with self.assertRaisesRegex(ValueError,"not pregame"):
   game_report(self.h,self.b,self.e,"2026-10-29T00:00:00Z",self.fixture)
 def test_reject_candidate_roster(self):
  self.e["lineup_type"]="candidate_roster"
  with self.assertRaisesRegex(ValueError,"Candidate"):
   game_report(self.h,self.b,self.e,"2026-10-28T19:00:00Z",self.fixture)
 def test_missing_player_produces_null(self):
  self.e["players"][0]["player_id"]=999
  x=game_report(self.h,self.b,self.e,"2026-10-28T19:00:00Z",self.fixture)
  self.assertIsNone(x["availability_delta"]["skater_offense"])
if __name__=="__main__":unittest.main()
