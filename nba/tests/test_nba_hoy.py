import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nba_hoy import assemble


class TestNbaHoy(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"content_sha256": "abc", "predictions": [
            {"game_id": "1", "tipoff_utc": "2026-10-26T00:00:00Z",
             "home_team": "BOS", "away_team": "NYK"},
            {"game_id": "2", "tipoff_utc": "2026-10-26T01:00:00Z",
             "home_team": "SAS", "away_team": "DEN"}]}
        self.integrated = {"statistical_snapshot_sha256": "abc", "predictions": [
            {"game_id": p["game_id"], "home_team": p["home_team"],
             "away_team": p["away_team"], "elo_p_home": 0.6,
             "challenger_p_home": 0.55, "hybrid_p_home": 0.57,
             "integrated_p_home": None, "evidence_checks": {},
             "all_sporting_steps_verified": False,
             "impact_model_independently_validated": False,
             "status": "statistical_baseline_only"}
            for p in self.snapshot["predictions"]]}

    def test_complete_slate_with_null_not_fabrication(self):
        result = assemble(self.snapshot, self.integrated)
        self.assertEqual(result["games_returned"], 2)
        self.assertFalse(result["all_final_probabilities_available"])
        self.assertTrue(all(x["final_p_home"] is None for x in result["games"]))

    def test_reject_missing_game(self):
        self.integrated["predictions"].pop()
        with self.assertRaises(ValueError):
            assemble(self.snapshot, self.integrated)

    def test_reject_unsupported_number(self):
        self.integrated["predictions"][0]["integrated_p_home"] = 0.61
        with self.assertRaises(ValueError):
            assemble(self.snapshot, self.integrated)

    def test_validated_candidate_has_complementary_probability(self):
        x = self.integrated["predictions"][0]
        x.update(integrated_p_home=0.62, all_sporting_steps_verified=True,
                 impact_model_independently_validated=True, status="integrated_candidate")
        result = assemble(self.snapshot, self.integrated)
        self.assertEqual(result["games"][0]["final_p_home"], 0.62)
        self.assertEqual(result["games"][0]["final_p_away"], 0.38)
        self.assertIsNone(result["games"][1]["final_p_home"])


if __name__ == "__main__":
    unittest.main()
