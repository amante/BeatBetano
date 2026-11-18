import unittest

from nhl.opponent_style_walkforward import (
    _valid_record,
    build_time_safe_features,
    home_win_probability,
)


def _counts(attempts, close):
    located = max(attempts, 1)
    close = min(close, located)
    return {
        "shot_events": attempts,
        "shots_on_goal": attempts // 2,
        "missed_shots": attempts // 4,
        "blocked_shot_events": attempts - attempts // 2 - attempts // 4,
        "goals": 3,
        "located_unblocked_shots": located,
        "distance_bins_ft": {"0-25": close, "25-40": located - close, "40+": 0},
    }


def _game(game_id, day, home, away, home_goals, away_goals,
          home_attempts=30, away_attempts=30, home_close=12, away_close=12):
    home_attack = _counts(home_attempts, home_close)
    away_attack = _counts(away_attempts, away_close)
    return {
        "game_id": str(game_id),
        "date": day,
        "home": home,
        "away": away,
        "result_final": {"home_goals": home_goals, "away_goals": away_goals},
        "opponent_style_features_version": 1,
        "opponent_style_profile": {
            "team_profiles": {
                home: {
                    "attack": home_attack,
                    "defense_allowed": away_attack,
                    "goal_attribution_check": {"matches_scoreboard": True},
                },
                away: {
                    "attack": away_attack,
                    "defense_allowed": home_attack,
                    "goal_attribution_check": {"matches_scoreboard": True},
                },
            },
        },
    }


class OpponentStyleWalkforwardTests(unittest.TestCase):
    def test_target_day_and_target_game_are_excluded(self):
        games = [
            _game(1, "2026-01-01", "NYR", "BOS", 2, 1,
                  home_attempts=24, away_attempts=27),
            _game(2, "2026-01-02", "MTL", "BUF", 1, 6,
                  home_attempts=10, away_attempts=60, home_close=2, away_close=50),
            _game(3, "2026-01-02", "FLA", "TOR", 8, 0,
                  home_attempts=70, away_attempts=5, home_close=60, away_close=1),
        ]
        first = {row["game_id"]: row for row in
                 build_time_safe_features(games, window=5, min_prior_games=0)}
        games[1]["result_final"] = {"home_goals": 0, "away_goals": 12}
        games[2]["result_final"] = {"home_goals": 0, "away_goals": 12}
        games[1]["opponent_style_profile"]["team_profiles"]["MTL"]["attack"]["shot_events"] = 999
        second = {row["game_id"]: row for row in
                  build_time_safe_features(games, window=5, min_prior_games=0)}
        self.assertEqual(first["2"]["prior_game_count"], 1)
        self.assertEqual(first["3"]["prior_game_count"], 1)
        for key in ("base_home_goals", "base_away_goals", "home_volume_ratio",
                    "away_volume_ratio", "home_close_delta", "away_close_delta"):
            self.assertEqual(first["2"][key], second["2"][key])
            self.assertEqual(first["3"][key], second["3"][key])

    def test_goal_mismatch_is_not_admitted_to_evaluation_archive(self):
        row = _game(1, "2026-01-01", "NYR", "BOS", 2, 1)
        valid, reason = _valid_record(row)
        self.assertTrue(valid)
        self.assertIsNone(reason)
        row["opponent_style_profile"]["team_profiles"]["NYR"][
            "goal_attribution_check"]["matches_scoreboard"] = False
        valid, reason = _valid_record(row)
        self.assertFalse(valid)
        self.assertEqual(reason, "goal_attribution_not_reconciled")

    def test_moneyline_probability_is_bounded_and_home_away_symmetric(self):
        probability = home_win_probability(4.0, 2.0)
        reverse = home_win_probability(2.0, 4.0)
        self.assertGreater(probability, 0.5)
        self.assertAlmostEqual(probability + reverse, 1.0, places=8)
        self.assertTrue(0.0 <= probability <= 1.0)


if __name__ == "__main__":
    unittest.main()
