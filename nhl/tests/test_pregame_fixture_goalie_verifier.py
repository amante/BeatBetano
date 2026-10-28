import unittest
from nhl.pregame_fixture_goalie_verifier import fixtures,verify
class PregameChecks(unittest.TestCase):
 def setUp(self):
  self.schedule={"captured_at":"2026-10-28T17:00:00Z","fixtures":[{"game_id":"101","home":"BOS","away":"MTL","scheduled_start":"2026-10-28T23:00:00Z","game_state":"FUT"}]}
  self.rosters=[{"team":"BOS","as_of":"2026-10-28T12:00:00Z","players":[{"player_id":11,"position_group":"goalie"}]}]
  self.obs={"game_id":"101","team":"BOS","player_id":11,"status":"probable","source_url":"https://example.org/goalies","as_of":"2026-10-28T16:00:00Z"}
 def test_fixture_parse(self):
  g=fixtures({"games":[{"id":101,"homeTeam":{"abbrev":"BOS"},"awayTeam":{"abbrev":"MTL"},"startTimeUTC":"2026-10-28T23:00:00Z","gameState":"FUT"}]},"2026-10-28")
  self.assertEqual(g[0]["game_id"],"101")
 def test_probable_kept_unconfirmed(self):
  x=verify(self.schedule,"101",self.obs,self.rosters)
  self.assertEqual(x["goalie_status"],"probable")
  self.assertFalse(x["eligible_for_full_crs"])
  self.assertFalse(x["confirmed_as_official"])
 def test_confirmed_requires_evidence(self):
  self.obs["status"]="confirmed"
  with self.assertRaisesRegex(ValueError,"evidence"):verify(self.schedule,"101",self.obs,self.rosters)
 def test_after_game_rejected(self):
  self.obs["as_of"]="2026-10-28T23:01:00Z"
  with self.assertRaises(ValueError):verify(self.schedule,"101",self.obs,self.rosters)
 def test_wrong_team_goalie_rejected(self):
  self.obs["player_id"]=999
  with self.assertRaises(ValueError):verify(self.schedule,"101",self.obs,self.rosters)
if __name__=="__main__":unittest.main()
