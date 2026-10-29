import unittest
from nhl.espn_goalie_provider_capture import extract,reconcile
class ESPNGoalieTests(unittest.TestCase):
 def setUp(self):
  self.meta={"source_url":"https://site.api.espn.com/scoreboard","retrieved_at":"2026-10-28T22:52:12Z"}
  self.source={"events":[{"id":"401892596","date":"2026-10-28T23:30Z","competitions":[{"competitors":[
   {"team":{"abbreviation":"WSH"},"homeAway":"home","probables":[{"name":"probableStartingGoalie","athlete":{"id":"4272888","displayName":"Logan Thompson"},"status":{"id":"102","name":"Confirmed","type":"confirmed"}}]},
   {"team":{"abbreviation":"PHI"},"homeAway":"away","probables":[{"name":"probableStartingGoalie","athlete":{"id":"4271575","displayName":"Joseph Woll"},"status":{"id":"101","type":"expected"}}]}]}]}]}
 def test_actual_espn_schema(self):
  x=extract(self.source,self.meta)
  self.assertEqual(x["confirmed_goalies"],1)
  self.assertEqual([v["goalie_status"] for v in x["observations"]],["confirmed","projected"])
  self.assertEqual(x["observations"][0]["provider_goalie_name"],"Logan Thompson")
  self.assertIsNone(x["observations"][0]["nhl_player_id"])
 def test_no_probables_fail_closed(self):
  self.source["events"][0]["competitions"][0]["competitors"][0].pop("probables")
  x=extract(self.source,self.meta)
  self.assertEqual(x["observations"][0]["goalie_status"],"unknown")
 def test_actual_mismatched_club_blocked(self):
  obs=extract(self.source,self.meta)
  rosters=[{"team":"WSH","as_of":"2026-10-28T20:00:00Z","players":[{"player_id":847,"full_name":"Logan Thompson","position_group":"goalie"}]},
    {"team":"PHI","as_of":"2026-10-28T20:00:00Z","players":[{"player_id":848,"full_name":"Someone Else","position_group":"goalie"}]}]
  schedule={"fixtures":[{"game_id":"2026020123","home":"WSH","away":"PHI","scheduled_start":"2026-10-28T23:30Z"}]}
  out=reconcile(obs,rosters,schedule)
  self.assertEqual(out["resolved_goalie_ids"],1)
  self.assertTrue(out["observations"][0]["usable_pregame_identity"])
  self.assertFalse(out["observations"][1]["usable_pregame_identity"])
  self.assertIn("goalie_name_unmatched_or_ambiguous",out["observations"][1]["validation_errors"])
  self.assertFalse(out["eligible_for_crs"])
 def test_late_capture_not_pregame(self):
  obs=extract(self.source,dict(self.meta,retrieved_at="2026-10-29T00:00:00Z"))
  rosters=[{"team":"WSH","as_of":"2026-10-28T20:00:00Z","players":[{"player_id":847,"full_name":"Logan Thompson","position_group":"goalie"}]}]
  sch={"fixtures":[{"game_id":"a","home":"WSH","away":"PHI","scheduled_start":"2026-10-28T23:30Z"}]}
  self.assertIn("source_after_start",reconcile(obs,rosters,sch)["observations"][0]["validation_errors"])
if __name__=="__main__":unittest.main()
