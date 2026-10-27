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

    def test_cached_evidence_resolves_observed_modules_without_fake_ratings(self):
        stamp = "2026-10-27T15:00:00Z"
        slate = {"sport":"nhl","as_of_utc":stamp,"events":[{"event_id":"9",
                 "home_team":"PHI","away_team":"CBJ"}]}
        goalies = {"sport":"nhl","as_of_utc":stamp,"games":{}}
        side = {"crs_evidence":{"games_played":8},
                "unit_evidence":{"forwards":{"players_with_stats":12},"defense":{"players_with_stats":7}},
                "goalie_evidence":{"candidates":[{"player_id":1}]},
                "special_teams_evidence":{"power_play_pct_observed":0.22,"penalty_kill_pct_observed":0.83}}
        cache = {"sport":"nhl","as_of_utc":stamp,"games":[{"event_id":"9","home_evidence":side,"away_evidence":side}]}
        result=review(slate,goalies,cache)["games"][0]
        self.assertEqual(result["modules"]["crs"]["state"],"observed_only")
        self.assertEqual(result["modules"]["unit_ratings"]["state"],"observed_only")
        self.assertEqual(result["modules"]["sustainable_pp_pk"]["state"],"observed_only")
        self.assertIsNone(result["official_win_probability"])
    def test_cached_evidence_wrong_timestamp_fails(self):
        slate={"sport":"nhl","as_of_utc":"2026-10-27T15:00:00Z","events":[]}
        goalie={"sport":"nhl","as_of_utc":slate["as_of_utc"],"games":{}}
        with self.assertRaises(ValueError):
            review(slate,goalie,{"sport":"nhl","as_of_utc":"2026-10-27T16:00:00Z","games":[]})

    def test_fails_closed_on_timestamp_mismatch(self):
        with self.assertRaises(ValueError):
            review({"sport": "nhl", "as_of_utc": "2026-10-27T00:00:00Z", "events": []},
                   {"sport": "nhl", "as_of_utc": "2026-10-28T00:00:00Z"})
if __name__ == "__main__":
    unittest.main()
