import unittest
from nhl.goalie_pregame_crosswalk import summarize
class CrosswalkTests(unittest.TestCase):
 def test_no_unknown_goalie_promoted(self):
  espn={"source":{"source_url":"https://site.api.espn.com/x","retrieved_at":"2026-10-28T20:00:00Z"},
    "observations":[{"espn_event_id":"1","team":"BOS","home_away":"home",
      "event_start":"2026-10-28T23:00:00Z","source_captured_at":"2026-10-28T20:00:00Z",
      "goalie_status":"confirmed","provider_goalie_name":"Test Goalie",
      "source_url":"https://site.api.espn.com/x"}]}
  roster=[{"team":"BOS","as_of":"2026-10-28T19:00:00Z","players":[{"player_id":123,"full_name":"Test Goalie","position_group":"goalie"}]}]
  schedule={"fixtures":[{"game_id":"100","home":"BOS","away":"MTL","scheduled_start":"2026-10-28T23:00:00Z"}]}
  x=summarize(espn,schedule,roster)
  self.assertEqual(x["summary"]["identity_linked"],1)
  self.assertEqual(x["summary"]["pregame_identity_usable"],1)
  self.assertFalse(x["full_crs_eligible"])
 def test_mismatched_team_unusable(self):
  espn={"source":{"source_url":"https://site.api.espn.com/x","retrieved_at":"2026-10-28T20:00:00Z"},
   "observations":[{"espn_event_id":"1","team":"BOS","home_away":"home",
     "event_start":"2026-10-28T23:00:00Z","source_captured_at":"2026-10-28T20:00:00Z",
     "goalie_status":"probable","provider_goalie_name":"Other Goalie"}]}
  schedule={"fixtures":[]}
  roster=[{"team":"BOS","as_of":"2026-10-28T19:00:00Z","players":[]}]
  x=summarize(espn,schedule,roster)
  self.assertEqual(x["summary"].get("pregame_identity_usable",0),0)
if __name__=="__main__":unittest.main()
