import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepared_history_gate import verify
H=[{"tipoff_utc":"2026-10-25T23:00:00Z"}]
A={"target_date":"2026-10-27","created_at_utc":"2026-10-26T18:00:00Z","source_count":1}
class Tests(unittest.TestCase):
 def test_good(self):
  self.assertEqual(verify("2026-10-27",H,A,{},{} )["historical_games"],1)
 def test_wrong_slate(self):
  with self.assertRaises(ValueError):verify("2026-10-28",H,A,{},{} )
 def test_same_day_leakage(self):
  with self.assertRaises(ValueError):verify("2026-10-27",[{"tipoff_utc":"2026-10-27T00:30:00Z"}],A,{},{} )
if __name__=="__main__":unittest.main()
 def test_us_previous_night_after_utc_midnight_is_excluded(self):
  from prepared_history_gate import prior_utc_history
  rows=[dict(game_id='1',tipoff_utc='2026-11-02T23:30:00Z'),dict(game_id='2',tipoff_utc='2026-11-03T00:30:00Z'),dict(game_id='3',tipoff_utc='2026-11-02T21:30:00-03:00')]
  kept,excluded=prior_utc_history(rows,'2026-11-03');self.assertEqual([r['game_id'] for r in kept],['1']);self.assertEqual(excluded,['2','3'])
 def test_exact_midnight_and_missing_timezone(self):
  from prepared_history_gate import prior_utc_history
  self.assertEqual(prior_utc_history([dict(game_id='1',tipoff_utc='2026-11-03T00:00:00Z')],'2026-11-03')[0],[])
  with self.assertRaises(ValueError):prior_utc_history([dict(tipoff_utc='2026-11-02T23:30:00')],'2026-11-03')
