import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibration_benchmark import metrics,compare_holdout
class Tests(unittest.TestCase):
    def test_coin_flip(self):
        r=metrics([(0.5,1),(0.5,0)])
        self.assertAlmostEqual(r["brier"],0.25)
        self.assertAlmostEqual(r["log_loss"],0.6931471805599453)
    def test_holdout_only(self):
        preds=[SimpleNamespace(game_id=str(y),season=y,p_home=0.75) for y in (2024,2025,2026)] + [SimpleNamespace(game_id="2024b",season=2024,p_home=0.5)]
        games=[{"game_id":str(y),"home_points":101,"away_points":95} for y in (2024,2025,2026)] + [{"game_id":"2024b","home_points":95,"away_points":101}]
        r=compare_holdout(preds,games)
        self.assertEqual(r["pooled"]["elo"]["n"],2)
        self.assertFalse(r["pooled"]["calibrated"])
        self.assertAlmostEqual(r["home_advantage_fit"]["home_win_rate"],0.5)
        self.assertIn("home_only_baseline",r["pooled"])
    def test_misalignment(self):
        with self.assertRaisesRegex(ValueError,"Misaligned"):
            compare_holdout([SimpleNamespace(game_id="warm1",season=2024,p_home=0.5),
                             SimpleNamespace(game_id="warm2",season=2024,p_home=0.5),
                             SimpleNamespace(game_id="x",season=2025,p_home=0.5)],
                            [{"game_id":"warm1","home_points":101,"away_points":95},
                             {"game_id":"warm2","home_points":95,"away_points":101},
                             {"game_id":"y","home_points":101,"away_points":95}])
if __name__=="__main__":unittest.main()
