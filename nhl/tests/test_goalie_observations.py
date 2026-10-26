import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_observations import integrate
F="2026-10-26T16:00:00Z"
S={"sport":"nhl","as_of_utc":F,"events":[{"event_id":"5","home_team":"BOS","away_team":"TOR","start_utc":"2026-10-27T00:00:00Z"}]}
def sample():
 return {"sport":"nhl","as_of_utc":F,"games":{"5":{"home":{"candidates":[{
 "goalie_id":"44","team":"BOS","source_url":"https://api-web.nhle.com/v1/player/44/game-log/20262027/2",
 "observed_at_utc":F,"starter_status":"unknown","official_confirmation":False,
 "shots_against":100,"saves":92,"sample_games":4,"gsax":None,"starts_last_7_days":2}]},
 "away":{"candidates":[]}}}}
class Test(unittest.TestCase):
 def test_real_observations_preserved(self):
  g=integrate(S,sample())["games"]["5"]
  self.assertEqual(g["home"]["goalie_candidates"][0]["save_percentage"],.92)
  self.assertFalse(g["home"]["starter_confirmed"])
  self.assertIsNone(g["win_probability_delta"])
 def test_stale_candidate_rejected(self):
  x=sample();x["games"]["5"]["home"]["candidates"][0]["observed_at_utc"]="2026-10-27T02:00:00Z"
  self.assertEqual(integrate(S,x)["games"]["5"]["home"]["goalie_candidates"],[])
 def test_different_freeze_rejected(self):
  x=sample();x["as_of_utc"]="2026-10-26T16:01:00Z"
  with self.assertRaises(ValueError):integrate(S,x)
 def test_duplicate_rejected(self):
  x=sample();a=x["games"]["5"]["home"]["candidates"];a.append(a[0].copy())
  with self.assertRaises(ValueError):integrate(S,x)
if __name__=="__main__":unittest.main()
