import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from walkforward import evaluate_history
class Tests(unittest.TestCase):
    def test_missing_seasons_rejected(self):
        g=[{"game_id":"G","season":2024,"tipoff_utc":"2023-11-01T00:00:00Z",
            "home_team":"BOS","away_team":"NYK","home_points":101,"away_points":100}]
        with self.assertRaisesRegex(ValueError,"three full"):
            evaluate_history(g)
    def test_mismatched_season_counts_are_not_certified(self):
        from datetime import datetime,timedelta,timezone
        rows=[]
        for year in (2024,2025,2026):
            start=datetime(year-1,10,20,tzinfo=timezone.utc)
            for i in range(2):
                rows.append({"game_id":f"{year}-{i}","season":year,
                             "tipoff_utc":(start+timedelta(days=i)).isoformat(),
                             "home_team":"BOS","away_team":"NYK",
                             "home_points":101,"away_points":100})
        result=evaluate_history(rows)
        self.assertFalse(result["coverage_verified"])
        self.assertIn("2024",result["coverage_discrepancies"])
    def test_no_results_rejected(self):
        with self.assertRaisesRegex(ValueError,"No NBA"):
            evaluate_history([])
if __name__=="__main__":unittest.main()
