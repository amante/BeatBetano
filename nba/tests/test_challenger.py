import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from challenger import predict_challenger
class Tests(unittest.TestCase):
    def test_first_game_no_outcome_leakage(self):
        rows=[{"game_id":"x","season":2024,"tipoff_utc":"2023-10-25T00:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":110,"away_points":90}]
        a=predict_challenger(rows)[0]
        rows[0]["home_points"],rows[0]["away_points"]=90,110
        b=predict_challenger(rows)[0]
        self.assertAlmostEqual(a["p_home"],b["p_home"])
        self.assertEqual(a["n_home"],0)
    def test_later_game_uses_prior_results(self):
        rows=[{"game_id":"x","season":2024,"tipoff_utc":"2023-10-25T00:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":110,"away_points":90},
              {"game_id":"y","season":2024,"tipoff_utc":"2023-10-28T00:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":None,"away_points":None}]
        r=predict_challenger(rows)
        self.assertEqual(r[1]["n_home"],1)
        self.assertEqual(r[1]["n_away"],1)
    def test_season_reset(self):
        rows=[{"game_id":"x","season":2024,"tipoff_utc":"2024-04-01T00:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":110,"away_points":90},
              {"game_id":"y","season":2025,"tipoff_utc":"2024-10-28T00:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":None,"away_points":None}]
        self.assertEqual(predict_challenger(rows)[1]["n_home"],0)
if __name__=="__main__":unittest.main()
