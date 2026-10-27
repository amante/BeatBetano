import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_feed import read_save_line,candidate_logs
from goalie_observations import integrate,summary

FREEZE="2026-10-27T17:00:00Z"
TIP="2026-10-27T23:00:00Z"
class Test(unittest.TestCase):
 def test_official_shots_goals_derives_saves(self):
  self.assertEqual(read_save_line({"shotsAgainst":32,"goalsAgainst":3}),(32,29))
  self.assertIsNone(read_save_line({"shotsAgainst":32,"goalsAgainst":3,"saves":30}))
 def test_prefreeze_stats_and_capture_coverage(self):
  payload={"gameLog":[{"gameDate":"2026-10-25","gameType":2,"shotsAgainst":32,"goalsAgainst":3},
                      {"gameDate":"2026-10-27","gameType":2,"shotsAgainst":20,"goalsAgainst":1}]}
  obs=candidate_logs({"goalies":[{"id":123}]},lambda url:payload,"BOS",FREEZE,TIP,20262027)
  self.assertEqual(obs[0]["saves"],29)
  self.assertEqual(obs[0]["sample_games"],1)
  slate={"sport":"nhl","as_of_utc":FREEZE,"events":[{"event_id":"5","home_team":"BOS","away_team":"TOR","start_utc":TIP}]}
  captured={"sport":"nhl","as_of_utc":FREEZE,"games":{"5":{"home":{"candidates":obs},"away":{"candidates":[]}}}}
  data=integrate(slate,captured)
  self.assertEqual(len(data["games"]["5"]["home"]["goalie_candidates"]),1)
  self.assertIn("recent_completed_games_only",summary(data))
  self.assertFalse(data["games"]["5"]["both_starters_confirmed"])
 def test_unrecognized_stat_line_visible(self):
  obs=candidate_logs({"goalies":[{"id":123}]},lambda u:{"gameLog":[{"gameDate":"2026-10-25","shotsAgainst":20}]},"BOS",FREEZE,TIP,20262027)
  self.assertEqual(obs[0]["data_status"],"unrecognized_game_log_stats")
  self.assertEqual(obs[0]["rejected_stat_rows"],1)
if __name__=="__main__":unittest.main()
