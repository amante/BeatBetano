import unittest
from nhl.pulso_sporting_bridge_226 import bridge
class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.report={"generated_at_utc":"2026-10-29T21:00:00Z",
   "games":[{"game_id":"123","home":"VGK","away":"NJD","start_utc":"2026-10-30T00:00:00Z"}]}
  self.rosters={"rosters":[{"team":"VGK","as_of":"2026-10-29T20:00:00Z"}]}
 def test_observation_not_confirmed(self):
  crosswalk={"retrieved_at":"2026-10-29T20:30:00Z","observations":[{"game_id":"123","team":"VGK","matchup_verified":True,"usable_pregame_identity":True,"nhl_player_id":42}]}
  t=bridge(self.report,crosswalk,self.rosters)["games"]["123"]["teams"]["VGK"]
  self.assertTrue(t["roster_identity_available"])
  self.assertEqual(t["provider_goalie_id_observed"],42)
  self.assertFalse(t["goalie_confirmed_independently"])
  self.assertIsNone(t["goalie_historical_rating"])
 def test_late_data_rejected(self):
  with self.assertRaises(ValueError):bridge(self.report,{"retrieved_at":"2026-10-29T22:00:00Z"},self.rosters)
 def test_no_fixture_link_no_attribution(self):
  t=bridge(self.report,{"observations":[{"game_id":"other","team":"VGK","matchup_verified":True}]},self.rosters)["games"]["123"]["teams"]["VGK"]
  self.assertEqual(t["provider_goalie_observation_count"],0)
if __name__=="__main__":unittest.main()
