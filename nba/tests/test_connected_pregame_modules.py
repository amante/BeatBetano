import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrated_model import integrate
from pulso_publication import build as build_publication
from pregame_module_bundle import player_matchup_context
from travel_context import build as build_travel


def seal(value):
    value["content_sha256"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return value


class ConnectedPregameModulesTests(unittest.TestCase):
    def snapshot(self):
        return seal({
            "created_at_utc": "2026-11-11T00:30:00Z",
            "predictions": [{
                "game_id": "g1", "tipoff_utc": "2026-11-12T00:00:00Z",
                "home_team": "BOS", "away_team": "NYK",
                "elo_p_home": 0.58, "challenger_p_home": 0.62,
                "hybrid_p_home": 0.58,
            }],
        })

    def test_matchup_context_joins_roster_position_without_claiming_defender(self):
        snapshot = self.snapshot()
        lineup = {"games": {"g1": {"teams": {
            "BOS": {"starters": ["Jayson Tatum"], "lineup_status": "projected",
                    "source_url": "https://example.test/lineup", "observed_at_utc": "2026-11-11T00:10:00Z"}
        }}}}
        roster = {"games": {"g1": {"teams": {
            "BOS": {"players": [{"player": "Jayson Tatum", "player_id": "1",
                                  "position_abbreviation": "SF", "position_name": "Small Forward"}]}
        }}}}
        result = player_matchup_context(snapshot, roster, lineup)["games"]["g1"]
        starter = result["teams"]["BOS"]["reported_starters"][0]
        self.assertEqual(starter["roster_match_status"], "unique_exact_name_match")
        self.assertEqual(starter["position"], "SF")
        self.assertFalse(result["teams"]["BOS"]["defensive_assignments_verified"])
        self.assertFalse(result["probabilities_adjusted"])

    def test_travel_context_reports_distance_and_timezone_without_adjusting_probability(self):
        snapshot = self.snapshot()
        snapshot.pop("content_sha256")
        snapshot["predictions"][0]["home_team"] = "NYK"
        snapshot["predictions"][0]["away_team"] = "BOS"
        seal(snapshot)
        history = [{
            "season": 2026, "game_id": "previous", "tipoff_utc": "2026-11-10T23:00:00Z",
            "home_team": "BOS", "away_team": "MIA", "home_points": 110, "away_points": 105,
        }]
        result = build_travel(snapshot, history)
        away = result["games"]["g1"]["teams"]["NYK"]
        self.assertEqual(away["status"], "no_prior_game_in_current_season")
        # Boston had its previous game at home and now travels to New York.
        home = result["games"]["g1"]["teams"]["BOS"]
        self.assertEqual(home["status"], "estimated_city_to_city_context")
        self.assertGreater(home["travel_distance_km"], 250)
        self.assertLess(home["travel_distance_km"], 350)
        self.assertTrue(home["timezone_zone_changed"])
        self.assertFalse(home["utc_offset_changed"])
        self.assertFalse(result["probabilities_adjusted"])

    def test_context_reaches_daily_model_but_cannot_change_baseline_probability(self):
        snapshot = self.snapshot()
        context = seal({
            "snapshot_sha256": snapshot["content_sha256"],
            "games": {"g1": {"travel_time_zones": {
                "connected": True, "affects_prediction": False, "data": {"status": "estimated"}
            }}},
        })
        result = integrate(snapshot, {}, module_context=context)
        prediction = result["predictions"][0]
        self.assertEqual(prediction["hybrid_p_home"], 0.58)
        self.assertIsNone(prediction["integrated_p_home"])
        self.assertEqual(prediction["supporting_modules"], context["games"]["g1"])
        self.assertFalse(result["modules_change_probabilities"])
        publication = build_publication(snapshot, "unit-run", context)
        self.assertEqual(publication["predictions"][0]["supporting_modules"], context["games"]["g1"])
        self.assertFalse(publication["modules_change_probabilities"])

    def test_tampered_context_is_rejected(self):
        snapshot = self.snapshot()
        context = seal({"snapshot_sha256": snapshot["content_sha256"], "games": {"g1": {}}})
        context["games"]["g1"]["travel_time_zones"] = {"affects_prediction": True}
        with self.assertRaises(ValueError):
            integrate(snapshot, {}, module_context=context)


if __name__ == "__main__":
    unittest.main()
