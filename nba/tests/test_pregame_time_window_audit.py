import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pregame_time_window_audit import audit
class Tests(unittest.TestCase):
 def test_start_before_tip_and_processing_after(self):
  x={"as_of_utc":"2026-10-27T01:59:40Z","future_fixtures":[{"game_id":"127","home_team":"DEN","away_team":"GS","tipoff_utc":"2026-10-27T02:00:00Z"}]}
  r=audit(x,"2026-10-27T02:02:49Z")
  self.assertEqual(r["initial_pregame_games"],1)
  self.assertEqual(r["crossed_tipoff"],1)
  self.assertFalse(r["games"][0]["still_pregame"])
if __name__=="__main__":unittest.main()
