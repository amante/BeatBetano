import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_daily import assess,matchup
F="2026-10-26T12:00:00Z";T="2026-10-27T00:00:00Z"
def sample():
 return {"team":"BOS","goalie_id":"1","source_url":"https://www.nhl.com/",
 "observed_at_utc":"2026-10-26T11:00:00Z","starter_status":"probable",
 "official_confirmation":False,"shots_against":100,"saves":91,
 "sample_games":4,"gsax":2.4,"starts_last_7_days":2}
class Test(unittest.TestCase):
 def test_measured_sv_and_gsax(self):
  x=assess(sample(),"BOS",F,T)
  self.assertEqual(x["save_percentage"],.91)
  self.assertEqual(x["gsax_per_game"],.6)
  self.assertIsNone(x["rating"])
 def test_probable_not_confirmed(self):
  self.assertFalse(assess(sample(),"BOS",F,T)["confirmed"])
 def test_confirmed_requires_official(self):
  x=sample();x["starter_status"]="confirmed"
  self.assertFalse(assess(x,"BOS",F,T)["confirmed"])
  x["official_confirmation"]=True
  self.assertTrue(assess(x,"BOS",F,T)["confirmed"])
 def test_late_rejected(self):
  x=sample();x["observed_at_utc"]="2026-10-26T13:00:00Z"
  self.assertIsNone(assess(x,"BOS",F,T)["rating"])
  self.assertEqual(assess(x,"BOS",F,T)["status"],"unverified_or_late")
 def test_no_invented_matchup_delta(self):
  x=matchup({"home":sample()},"BOS","TOR",F,T)
  self.assertIsNone(x["calibrated_goalie_impact"])
if __name__=="__main__":unittest.main()
