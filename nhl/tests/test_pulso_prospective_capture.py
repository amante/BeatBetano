import unittest
from datetime import datetime,timedelta,timezone
from nhl.pulso_prospective_capture import assemble,capture_rosters
class TestCapture(unittest.TestCase):
 def test_future_is_unavailable_without_verified_lineups(self):
  now=datetime.now(timezone.utc)
  start=(now+timedelta(hours=4)).isoformat()
  schedule={"fixtures":[{"game_id":"123","home":"EDM","away":"COL","scheduled_start":start,"game_state":"FUT"}]}
  observations=[{"team":"EDM","event_start":start,"goalie_status":"confirmed","provider_goalie_name":"Example"}]
  output=assemble(schedule,observations,now.isoformat())
  self.assertEqual(len(output),1)
  self.assertEqual(output[0]["status"],"unavailable")
  self.assertEqual(output[0]["goalie_provider_observations"]["EDM"]["status"],"confirmed")
  self.assertIsNone(output[0]["probabilities"])
  self.assertFalse(output[0]["goalie_provider_observations"]["EDM"]["confirmed_as_official"])
  self.assertEqual(output[0]["goalie_provider_observations"]["COL"]["status"],"unknown")
 def test_full_espn_report_is_rejected(self):
  with self.assertRaises(ValueError):assemble({"fixtures":[]},{"observations":[]})
 def test_roster_fetch_preserves_unknown_lineups(self):
  now=datetime.now(timezone.utc)
  start=(now+timedelta(hours=4)).isoformat()
  schedule={"fixtures":[{"game_id":"3","home":"EDM","away":"COL","scheduled_start":start,"game_state":"FUT"}]}
  calls=[]
  def fake(team):
   calls.append(team)
   return {"team":team,"as_of":now.isoformat(),"players":[],"lineup_confirmed":False}
  rows,errors=capture_rosters(schedule,now.isoformat(),fake)
  self.assertEqual(len(rows),2)
  self.assertEqual(errors,{})
  self.assertTrue(all(r["lineup_confirmed"] is False for r in rows))
 def test_missing_roster_fails_closed(self):
  now=datetime.now(timezone.utc)
  schedule={"fixtures":[{"game_id":"3","home":"EDM","away":"COL","scheduled_start":(now+timedelta(hours=4)).isoformat(),"game_state":"FUT"}]}
  def fetch(team):
   if team=="COL":raise ValueError("source unavailable")
   return {"team":team,"as_of":now.isoformat()}
  rows,errors=capture_rosters(schedule,now.isoformat(),fetch)
  self.assertEqual(len(rows),1);self.assertIn("COL",errors)
 def test_started_game_is_not_republished(self):
  now=datetime.now(timezone.utc)
  schedule={"fixtures":[{"game_id":"1","home":"EDM","away":"COL","scheduled_start":(now-timedelta(seconds=1)).isoformat(),"game_state":"FUT"}]}
  self.assertEqual(assemble(schedule,[],now.isoformat()),[])
if __name__=="__main__":unittest.main()
