import unittest
from nhl.pulso_goalie_multisource_257 import extract,TEAM_NAMES
class ExternalGoalie257(unittest.TestCase):
 def setUp(self):
  self.report={"generated_at_utc":"2026-10-31T14:00:00Z","games":[{"game_id":"1","home":"BOS","away":"CHI","start_utc":"2026-10-31T21:00:00Z"}]}
  self.rosters={"rosters":[{"team":"BOS","players":[{"player_id":123,"full_name":"Michael DiPietro","position_group":"goalie"}]},
   {"team":"CHI","players":[{"player_id":456,"full_name":"Arvid Soderblom","position_group":"goalie"}]}]}
  self.meta={"retrieved_at":"2026-10-31T16:00:00Z","source_url":"https://www.dailyfaceoff.com/starting-goalies","sha256":"test"}
  self.lines=["Chicago Blackhawks at Boston Bruins","2026-10-31T21:00:00Z",
   "Arvid Soderblom","Unconfirmed","Michael DiPietro","Confirmed","2026-10-31T15:41:40Z"]
 def test_named_candidate_and_status(self):
  x=extract(self.lines,self.report,self.rosters,self.meta)
  self.assertEqual(len(x["observations"]),2)
  self.assertEqual(x["observations"][1]["name"],"Michael DiPietro")
  self.assertFalse(x["observations"][1]["independent_nhl_confirmation"])
 def test_after_puck_drop_is_not_used(self):
  self.meta["retrieved_at"]="2026-10-31T21:01:00Z"
  self.assertEqual(extract(self.lines,self.report,self.rosters,self.meta)["observations"],[])
 def test_unknown_name_not_promoted(self):
  self.lines[4]="Unidentified Goalie"
  x=extract(self.lines,self.report,self.rosters,self.meta)
  self.assertEqual(len(x["observations"]),1)
 def test_provider_timestamp_after_capture_rejected(self):
  self.lines[-1]="2026-10-31T19:00:00Z"
  x=extract(self.lines,self.report,self.rosters,self.meta)
  self.assertEqual(len(x["observations"]),1)
if __name__=="__main__":unittest.main()
