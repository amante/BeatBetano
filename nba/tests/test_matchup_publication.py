import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulso_publication import build, digest


class PlayerMatchupPublicationTests(unittest.TestCase):
    def setUp(self):
        snapshot_body = {
            "created_at_utc": "2026-11-10T19:00:00Z",
            "predictions": [{"game_id": "g1", "home_team": "BOS", "away_team": "NYK",
                "tipoff_utc": "2026-11-10T23:00:00Z",
                "elo_p_home": 0.52, "challenger_p_home": 0.51, "hybrid_p_home": 0.515}],
        }
        self.snapshot = dict(snapshot_body, content_sha256=digest(snapshot_body))
        context_body = {"snapshot_sha256": self.snapshot["content_sha256"], "games": {
            "g1": {"player_matchups": {"status": "available_not_used",
                "affects_prediction": False, "entered_prediction": False}}}}
        self.context = dict(context_body, content_sha256=digest(context_body))
        delta = 0.1
        base = 0.515
        adjusted = 1.0 / (1.0 + math.exp(-(math.log(base / (1 - base)) + delta)))
        candidate = {"game_id": "g1", "base_home_probability": base,
            "adjusted_home_probability": adjusted, "status": "research_scenario",
            "applied": True, "log_odds_delta": delta,
            "assignment_method": "minimum_position_distance_estimate",
            "assignments_verified": False}
        body = {"schema_version": 1, "snapshot_sha256": self.snapshot["content_sha256"],
            "created_at_utc": self.snapshot["created_at_utc"], "games": [candidate],
            "calibrated": False, "production_approved": False,
            "assignments_verified": False, "no_odds_input": True}
        self.matchups = dict(body, content_sha256=digest(body))

    def test_matchup_delta_changes_published_candidate_and_module_status(self):
        result = build(self.snapshot, "test-run", self.context,
                       matchup_adjustment=self.matchups)
        prediction = result["predictions"][0]
        self.assertGreater(prediction["model_p_home"], self.snapshot["predictions"][0]["hybrid_p_home"])
        self.assertEqual(prediction["probability_adjustments_applied"], ["matchup"])
        self.assertEqual(prediction["supporting_modules"]["player_matchups"]["status"],
                         "research_scenario")
        self.assertTrue(prediction["supporting_modules"]["player_matchups"]["affects_prediction"])
        self.assertFalse(result["calibrated"])

    def test_invalid_large_matchup_delta_is_rejected(self):
        data = dict(self.matchups)
        data["games"] = [dict(self.matchups["games"][0], log_odds_delta=0.5)]
        body = {k: v for k, v in data.items() if k != "content_sha256"}
        data["content_sha256"] = digest(body)
        with self.assertRaisesRegex(ValueError, "Invalid bounded matchup"):
            build(self.snapshot, "test-run", self.context, matchup_adjustment=data)


if __name__ == "__main__":
    unittest.main()
