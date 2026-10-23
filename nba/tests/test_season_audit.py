import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from season_audit import audit

class Tests(unittest.TestCase):
    def test_surplus_detected_without_removing_games(self):
        games=[{"game_id":str(i),"season":2026,"tipoff_utc":"2026-01-01T00:00:00Z",
                "home_team":"BOS","away_team":"NYK"} for i in range(84)]
        a=audit(games)["2026"]
        self.assertEqual(a["games"],84)
        self.assertEqual(a["team_over_82"],{"BOS":2,"NYK":2})
        self.assertFalse(a["coverage_verified"])
        self.assertEqual(len(a["candidate_games_requiring_source_review"]),84)
    def test_empty(self):
        self.assertEqual(audit([]),{})
if __name__=="__main__":unittest.main()
