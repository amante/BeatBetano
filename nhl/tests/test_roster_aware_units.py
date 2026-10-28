import unittest
from nhl.roster_aware_units import assess
class UnitsTests(unittest.TestCase):
 def setUp(self):
  self.past={"team":"BOS","players":{"101":{"observed":4,"goals":2,"shots":12,"role":"skater"},"202":{"observed":0,"role":"goalie"}}}
  self.lineup={"team":"BOS","source":"dated expected lines","as_of":"2026-10-28T12:00:00Z",
    "players":[{"player_id":101,"unit":"top6","status":"projected","expected_share":.8},
               {"player_id":202,"unit":"goalie","status":"confirmed","expected_share":1.},
               {"player_id":303,"unit":"top4_d","status":"out","expected_share":0.}]}
 def test_descriptive_units_with_missing_goalie(self):
  x=assess(self.past,self.lineup,"2026-10-28T16:00:00Z")
  self.assertEqual(x["units"]["top6"]["historic_weighted_goals_per_player_game"],.5)
  self.assertEqual(x["units"]["goalie"]["missing_player_ids"],[202])
  self.assertIsNone(x["crs_numeric_rating"])
  self.assertIsNone(x["availability_delta"])
 def test_future_lineup_rejected(self):
  with self.assertRaisesRegex(ValueError,"Future"):
   assess(self.past,self.lineup,"2026-10-27T18:00:00Z")
 def test_out_player_cannot_be_projected_to_play(self):
  self.lineup["players"][2]["expected_share"]=.5
  with self.assertRaisesRegex(ValueError,"Unavailable"):
   assess(self.past,self.lineup,"2026-10-28T16:00:00Z")
 def test_duplicate_ids_rejected(self):
  self.lineup["players"].append(dict(self.lineup["players"][0]))
  with self.assertRaisesRegex(ValueError,"duplicate"):
   assess(self.past,self.lineup,"2026-10-28T16:00:00Z")
if __name__=="__main__":unittest.main()
