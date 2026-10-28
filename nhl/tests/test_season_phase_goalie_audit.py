import unittest
from nhl.season_phase_goalie_audit import phase_counts,average
class SeasonPhaseAuditTests(unittest.TestCase):
 def test_same_date_does_not_advance_other_fixture(self):
  rows=[{"game_id":"1","date":"2025-10-01","home":"BOS","away":"MTL"},
        {"game_id":"2","date":"2025-10-01","home":"BOS","away":"TOR"},
        {"game_id":"3","date":"2025-10-03","home":"BOS","away":"MTL"}]
  out=phase_counts(rows)
  self.assertEqual(out["1"]["home_game_number"],1)
  self.assertEqual(out["2"]["home_game_number"],1)
  self.assertEqual(out["3"]["home_game_number"],3)
 def test_new_season_resets(self):
  rows=[{"game_id":"a","date":"2025-04-01","home":"BOS","away":"TOR"},
        {"game_id":"b","date":"2025-10-01","home":"BOS","away":"TOR"}]
  x=phase_counts(rows)
  self.assertEqual(x["b"]["home_game_number"],1)
 def test_empty_phase(self):
  self.assertEqual(average([])["n"],0)
if __name__=="__main__":unittest.main()
