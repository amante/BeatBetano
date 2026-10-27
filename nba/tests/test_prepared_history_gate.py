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
