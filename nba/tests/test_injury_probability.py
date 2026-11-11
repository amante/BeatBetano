import hashlib
import json
import unittest

from nba.injury_probability import build


def seal(document):
    body = dict(document)
    body.pop("content_sha256", None)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    body["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return body


def team(out_count=0, points_lost=0.0, points_added=0.0, out_players=None):
    return {
        "official_report_fixture_rows": 2,
        "roster_complete": True,
        "conflicting_official_claims": [],
        "official_out_count": out_count,
        "historical_output_loss_per_game": {"points": points_lost},
        "historical_output_from_added_minutes_per_game": (
            {"points": points_added} if out_count else None
        ),
        "minute_redistribution": {
            "status": "conditional_historical_rotation_scenario" if out_count else "no_official_out_players"
        },
        "players_without_historical_minutes": [],
        "replacement_history_gaps": [],
        "official_reported_players": out_players or [],
        "players_without_confirmed_availability": 3,
    }


class ConfirmedInjuryProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.gid = "game-1"
        self.snapshot = seal({
            "created_at_utc": "2026-11-11T20:00:00Z",
            "predictions": [{
                "game_id": self.gid, "tipoff_utc": "2026-11-11T23:00:00Z",
                "home_team": "BOS", "away_team": "MIA", "hybrid_p_home": 0.58
            }]
        })
        scenario = {
            "baseline_snapshot_sha256": self.snapshot["content_sha256"],
            "games": {self.gid: {"teams": {
                "BOS": team(1, 24.0, 17.0, [{"player": "Home Star", "player_id": "h1", "official_status": "out"}]),
                "MIA": team()
            }}}
        }
        self.context = seal({
            "snapshot_sha256": self.snapshot["content_sha256"],
            "games": {self.gid: {"availability_impact": {
                "conditional_production_scenario": scenario
            }}}
        })
        self.history = [{
            "game_id": str(i), "tipoff_utc": "2026-10-01T00:00:00Z",
            "observed_at_utc": "2026-10-02T00:00:00Z",
            "home_points": 110 + (i % 2) * 10, "away_points": 110 - (i % 2) * 10
        } for i in range(100)]

    def test_confirmed_out_changes_only_research_candidate(self):
        report = build(self.snapshot, self.context, self.history)
        game = report["games"][0]
        self.assertEqual(game["status"], "research_scenario")
        self.assertLess(game["injury_adjusted_home_probability"], game["base_home_probability"])
        self.assertEqual(game["base_home_probability"], 0.58)
        self.assertFalse(game["base_prediction_changed"])
        self.assertFalse(report["production_approved"])
        self.assertEqual(game["teams"]["BOS"]["out_players"][0]["player"], "Home Star")

    def test_short_margin_history_blocks_probability_calculation(self):
        report = build(self.snapshot, self.context, self.history[:99])
        self.assertEqual(report["games"][0]["status"], "blocked")
        self.assertIn("fewer_than_100", report["games"][0]["reason"])
        self.assertIsNone(report["games"][0]["injury_adjusted_home_probability"])

    def test_future_games_do_not_enter_margin_scale(self):
        future = dict(self.history[0], game_id="future", tipoff_utc="2026-11-12T00:00:00Z")
        report = build(self.snapshot, self.context, self.history[:99] + [future])
        self.assertEqual(report["games"][0]["margin_sample_games"], 99)
        self.assertEqual(report["games"][0]["status"], "blocked")

    def test_missing_official_report_match_blocks_adjustment(self):
        scenario = self.context["games"][self.gid]["availability_impact"]["conditional_production_scenario"]
        scenario["games"][self.gid]["teams"]["BOS"]["official_report_fixture_rows"] = 0
        self.context = seal(self.context)
        report = build(self.snapshot, self.context, self.history)
        self.assertEqual(report["games"][0]["status"], "blocked")
        self.assertIn("no_official_report_row_for_team", report["games"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
