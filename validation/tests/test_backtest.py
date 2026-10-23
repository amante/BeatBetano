"""Deterministic smoke tests; synthetic data is NOT historical evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import brier, logloss, nfl, nba20


class ValidationTests(unittest.TestCase):
    def test_probabilistic_metrics(self):
        self.assertAlmostEqual(brier([0.8, 0.3], [1, 0]), 0.065)
        self.assertGreater(logloss([0.5, 0.5], [1, 0]), 0)
        self.assertLess(logloss([0.9, 0.1], [1, 0]), logloss([0.5, 0.5], [1, 0]))

    def test_nba_20_is_in_game_not_final_margin(self):
        with tempfile.TemporaryDirectory() as temp:
            inp = Path(temp) / "pbp.csv"
            out = Path(temp) / "out"
            pd.DataFrame([
                {"game_id":"g1","home_score":0,"away_score":0},
                {"game_id":"g1","home_score":50,"away_score":29},
                {"game_id":"g1","home_score":101,"away_score":103},
                {"game_id":"g2","home_score":50,"away_score":40},
                {"game_id":"g2","home_score":98,"away_score":91},
            ]).to_csv(inp,index=False)
            nba20(inp,out)
            records = pd.read_csv(out / "nba_20_events.csv")
            self.assertEqual(records.set_index("game_id").loc["g1","any_20_plus"],1)
            self.assertEqual(records.set_index("game_id").loc["g2","any_20_plus"],0)
            self.assertEqual(json.loads((out/"summary.json").read_text())["games_with_20_plus"],1)

    def test_nfl_predictions_frozen_before_score_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            inp = Path(temp) / "games.csv"
            out = Path(temp) / "out"
            pd.DataFrame([
                {"season":2023,"gameday":"2023-09-10","week":1,"game_type":"REG","home_team":"A","away_team":"B","home_score":21,"away_score":14},
                {"season":2023,"gameday":"2023-09-10","week":1,"game_type":"REG","home_team":"A","away_team":"C","home_score":30,"away_score":14},
                {"season":2024,"gameday":"2024-09-10","week":1,"game_type":"REG","home_team":"B","away_team":"A","home_score":24,"away_score":14},
                {"season":2025,"gameday":"2025-09-10","week":1,"game_type":"REG","home_team":"A","away_team":"B","home_score":19,"away_score":18},
            ]).to_csv(inp,index=False)
            nfl(inp,out)
            p = pd.read_csv(out / "pregame_predictions.csv")
            self.assertAlmostEqual(p.iloc[0].p_home, p.iloc[1].p_home)
            metrics=json.loads((out/"metrics.json").read_text())
            self.assertEqual(metrics["games"],4)
            self.assertEqual(metrics["test_seasons"],[2025])
            self.assertTrue(0 <= metrics["brier"] <= 1)

    def test_missing_data_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp:
            inp=Path(temp)/"bad.csv"
            pd.DataFrame([{"game_id":"x"}]).to_csv(inp,index=False)
            with self.assertRaises(ValueError):
                nba20(inp, Path(temp)/"out")


if __name__ == "__main__":
    unittest.main()
