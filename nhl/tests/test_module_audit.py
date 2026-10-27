import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module_audit import MODULES, context, review, markdown

class ModuleAuditTests(unittest.TestCase):
    def test_rivalry_and_division(self):
        self.assertTrue(context("BOS", "MTL")["divisional"])
        self.assertEqual(context("BOS", "MTL")["rivalry_tier"], "A")
        self.assertFalse(context("BOS", "DAL")["divisional"])
        self.assertIsNone(context("BOS", "DAL")["rivalry_tier"])
        self.assertTrue(context("COL", "WPG")["divisional"])

    def test_all_ten_modules_and_no_false_promotion(self):
        slate = {"sport": "nhl", "as_of_utc": "2026-10-27T15:00:00Z",
                 "events": [{"event_id": "123", "home_team": "BOS", "away_team": "MTL",
                             "statistical_p_home": 0.87, "official_baseline": None,
                             "official_team_stats": {"home": {}, "away": {}}}]}
        goalies = {"sport": "nhl", "as_of_utc": slate["as_of_utc"], "games": {}}
        result = review(slate, goalies)
        game = result["games"][0]
        self.assertEqual(set(game["modules"]), set(MODULES))
        self.assertIsNone(game["official_win_probability"])
        self.assertFalse(game["eligible_for_bet"])
        self.assertEqual(game["modules"]["division_rivalry"]["context"]["rivalry_tier"], "A")
        self.assertIn("MTL @ BOS", markdown(result))

    def test_fails_closed_on_timestamp_mismatch(self):
        with self.assertRaises(ValueError):
            review({"sport": "nhl", "as_of_utc": "2026-10-27T00:00:00Z", "events": []},
                   {"sport": "nhl", "as_of_utc": "2026-10-28T00:00:00Z"})
if __name__ == "__main__":
    unittest.main()
