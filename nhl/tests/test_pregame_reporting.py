import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pregame_reporting import report
class Test(unittest.TestCase):
 def test_observed_data_visible_not_calibrated(self):
  def team():
   return {"unit_evidence":{"forwards":{"players_with_stats":12},"defense":{"players_with_stats":7}},
    "goalie_evidence":{"candidates":[{},{}]},
    "special_teams_evidence":{"power_play_pct_observed":0.25,"penalty_kill_pct_observed":0.83}}
  row={"games":[{"home_team":"PHI","away_team":"CBJ",
   "home_evidence":team(),"away_evidence":team()}],"snapshot_age_hours":0.2}
  md,counts=report(row)
  self.assertIn("12/7 / 12/7",md)
  self.assertIn("0.25 / 0.25",md)
  self.assertIn("Not calibrated",md)
  self.assertEqual(counts["teams_with_pp_pk"],2)
 def test_empty_slate_rejected(self):
  with self.assertRaises(ValueError):report({"games":[]})
if __name__=="__main__":unittest.main()
