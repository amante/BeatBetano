import unittest
from nhl.official_roster_snapshot import TEAMS
from nhl.individual_roster_indices import evaluate
class IndividualIndicesTests(unittest.TestCase):
 def setUp(self):
  self.h={"team":"BOS","players":{
   "1":{"role":"skater","skater_games":5,"skater_goals":2,"skater_shots":15,"toi_games":5,"toi_seconds":6000},
   "2":{"role":"skater","skater_games":5,"skater_goals":1,"skater_shots":10,"toi_games":5,"toi_seconds":4500},
   "3":{"role":"goalie","goalie_games":5,"goalie_saves":135,"goalie_shots":150,"toi_games":5,"toi_seconds":18000}}}
  self.base={"team":"BOS","source_url":"https://example.org/lineup","as_of":"2026-10-28T12:00:00Z","lineup_type":"projected",
    "players":[{"player_id":1,"unit":"top6","status":"projected","expected_share":1.},
               {"player_id":3,"unit":"goalie","status":"projected","expected_share":1.}]}
  self.new=dict(self.base,players=[{"player_id":2,"unit":"top6","status":"projected","expected_share":1.},
                {"player_id":3,"unit":"goalie","status":"projected","expected_share":1.}])
 def test_32_teams(self):
  self.assertEqual(len(TEAMS),32)
  self.assertEqual(len(set(TEAMS)),32)
 def test_goalie_toi_and_roster_delta(self):
  x=evaluate(self.h,self.base,self.new,"2026-10-28T18:00:00Z")
  self.assertAlmostEqual(x["expected"]["indices"]["goalie_save_pct_weighted"],.9)
  self.assertEqual(x["expected"]["indices"]["skater_toi_minutes"],15.)
  self.assertAlmostEqual(x["availability_delta"]["skater_offense"],-.25)
  self.assertEqual(x["availability_delta"]["skater_toi_minutes"],-5.)
  self.assertIsNone(x["full_crs_numeric_rating"])
 def test_missing_player_not_imputed(self):
  self.new["players"][0]["player_id"]=999
  x=evaluate(self.h,self.base,self.new,"2026-10-28T18:00:00Z")
  self.assertIsNone(x["availability_delta"]["skater_offense"])
  self.assertIsNone(x["availability_delta"]["skater_toi_minutes"])
 def test_later_snapshot_rejected(self):
  self.new["as_of"]="2026-10-29T12:00:00Z"
  with self.assertRaises(ValueError):evaluate(self.h,self.base,self.new,"2026-10-28T18:00:00Z")
if __name__=="__main__":unittest.main()
