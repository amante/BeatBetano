import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from travel_probability import _apply_fit, _travel_rows


class TravelFeatureTests(unittest.TestCase):
    def test_consecutive_away_venues_are_tracked_from_actual_prior_arena(self):
        rows = [
            {"game_id": "1", "tipoff_utc": "2026-11-01T00:00:00Z", "home_team": "BOS", "away_team": "NY"},
            {"game_id": "2", "tipoff_utc": "2026-11-03T00:00:00Z", "home_team": "CHI", "away_team": "BOS"},
            {"game_id": "3", "tipoff_utc": "2026-11-05T00:00:00Z", "home_team": "DEN", "away_team": "BOS"},
            {"game_id": "4", "tipoff_utc": "2026-11-07T00:00:00Z", "home_team": "BOS", "away_team": "NY"},
        ]
        features = {row["game_id"]: row for row in _travel_rows(rows)}
        self.assertIn("4", features)
        # Boston's previous venue was Denver, not Chicago or New York.
        self.assertLess(features["4"]["distance_imbalance_1000km"], 0)

    def test_holdout_rejects_nonpredictive_travel_features(self):
        random.seed(11)
        rows = []
        for index in range(800):
            x = random.uniform(-2, 2)
            y = random.uniform(-1, 1)
            rows.append(({"distance_imbalance_1000km": x,
                          "timezone_shift_imbalance_hours": y}, (0.0, index % 2)))
        result = _apply_fit(rows)
        self.assertFalse(result["applied"])

    def test_fit_has_bounded_two_feature_weights(self):
        samples = [({"distance_imbalance_1000km": float(i % 3),
                     "timezone_shift_imbalance_hours": float((i % 5)-2)},
                    (0.0, int(i % 7 < 4))) for i in range(700)]
        fit = _apply_fit(samples)
        self.assertIn(fit["status"], {"holdout_no_improvement", "research_adjustment_validated_on_chronological_holdout"})
        if fit["applied"]:
            self.assertTrue(all(math.isfinite(value) for value in fit["fit"]["coefficients_standardized"]))


if __name__ == "__main__":
    unittest.main()
