import unittest
from nhl.espn_goalie_provider_capture import extract
class ESPNGoalieTests(unittest.TestCase):
 def setUp(self):
  self.meta={"source_url":"https://site.api.espn.com/scoreboard","retrieved_at":"2026-10-28T14:00:00Z"}
 def test_unknown_schema_fails_closed(self):
  src={"events":[{"id":"1","competitions":[{"competitors":[{"team":{"abbreviation":"BOS"}}]}]}]}
  x=extract(src,self.meta)
  self.assertEqual(x["observations"][0]["goalie_status"],"unknown")
  self.assertFalse(x["eligible_for_crs"])
 def test_explicit_report_not_official_confirmation(self):
  src={"events":[{"id":"1","competitions":[{"competitors":[{"team":{"abbreviation":"MTL"},
    "probableStarter":{"athlete":{"id":"123","displayName":"A Goalie"},"status":"confirmed"}}]}]}]}
  x=extract(src,self.meta)
  self.assertEqual(x["confirmed_goalies"],1)
  self.assertIsNone(x["observations"][0]["nhl_player_id"])
  self.assertFalse(x["observations"][0]["eligible_for_crs"])
 def test_reject_missing_events(self):
  with self.assertRaisesRegex(ValueError,"Missing events"):extract({},self.meta)
if __name__=="__main__":unittest.main()
