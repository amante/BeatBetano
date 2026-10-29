import unittest
from datetime import datetime,timedelta,timezone
from nhl.pulso_prospective_capture import assemble
class TestCapture(unittest.TestCase):
 def test_future_is_unavailable_without_verified_lineups(self):
  now=datetime.now(timezone.utc)
  start=(now+timedelta(hours=4)).isoformat()
  schedule={"fixtures":[{"game_id":"123","home":"EDM","away":"COL","scheduled_start":start,"game_state":"FUT"}]}
  observations=[{"team":"EDM","event_start":start,"status":"confirmed","provider_goalie_name":"Example"}]
  output=assemble(schedule,observations,now.isoformat())
  self.assertEqual(len(output),1)
  self.assertEqual(output[0]["status"],"unavailable")
  self.assertIsNone(output[0]["probabilities"])
  self.assertFalse(output[0]["goalie_provider_observations"]["EDM"]["confirmed_as_official"])
  self.assertEqual(output[0]["goalie_provider_observations"]["COL"]["status"],"unknown")
 def test_started_game_is_not_republished(self):
  now=datetime.now(timezone.utc)
  schedule={"fixtures":[{"game_id":"1","home":"EDM","away":"COL","scheduled_start":(now-timedelta(seconds=1)).isoformat(),"game_state":"FUT"}]}
  self.assertEqual(assemble(schedule,[],now.isoformat()),[])
if __name__=="__main__":unittest.main()
