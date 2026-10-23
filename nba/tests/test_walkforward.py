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
    def test_no_results_rejected(self):
        with self.assertRaisesRegex(ValueError,"No NBA"):
            evaluate_history([])
if __name__=="__main__":unittest.main()
