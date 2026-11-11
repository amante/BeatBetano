import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_injury_impact import build


class OfficialInjuryImpactTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "content_sha256": "snapshot-1",
            "created_at_utc": "2026-11-10T17:00:00Z",
            "predictions": [{"game_id": "g1", "tipoff_utc": "2026-11-10T22:00:00Z",
                             "home_team": "BOS", "away_team": "NYK"}],
        }
        players = []
        rotation = []
        history = []
        for index in range(6):
            pid = str(index + 1)
            sources = []
            if index == 0:
                sources.append({
                    "url": "https://ak-static.cms.nba.com/referee/injury/report.pdf",
                    "status": "Out", "observed_at_utc": "2026-11-10T18:00:00Z",
                    "reported_at_utc": "2026-11-10T17:45:00Z",
                    "confidence": "official_nba_injury_report_unique_roster_match",
                })
            players.append({"player_id": pid, "player": f"Player {pid}",
                            "status": "out" if index == 0 else "unknown",
                            "status_sources": sources})
            rotation.append({"player_id": pid, "player": f"Player {pid}",
                             "minutes_projection": 40, "sample_games": 4})
            for game_index in range(3):
                history.append({
                    "player_id": pid, "team": "BOS", "minutes_played": 30,
                    "points": 15, "rebounds": 5, "assists": 4, "turnovers": 2,
                    "tipoff_utc": f"2026-11-{7 + game_index:02d}T22:00:00Z",
                    "observed_at_utc": f"2026-11-{8 + game_index:02d}T01:00:00Z",
                })
        self.availability = {
            "snapshot_sha256": "snapshot-1",
            "games": {"g1": {"teams": {
                "BOS": {"roster_complete": True, "players": players,
                        "players_without_confirmed_availability": 5},
                "NYK": {"roster_complete": True, "players": [],
                        "players_without_confirmed_availability": 0},
            }}},
            "official_report_evidence": {"rows_by_fixture": [
                {"game_id": "g1", "status": "rows_selected", "fixture_team_rows": 1}
            ]},
        }
        self.rotation = {"snapshot_sha256": "snapshot-1", "games": {"g1": {"teams": {
            "BOS": {"provisional_rotation": rotation},
            "NYK": {"provisional_rotation": []},
        }}}}
        self.history = {"players": history}

    def test_official_out_creates_conditional_minutes_and_outputs_without_changing_probabilities(self):
        result = build(self.snapshot, self.availability, self.rotation, self.history,
                       "2026-11-10T19:00:00Z")
        game = result["games"]["g1"]
        home = game["teams"]["BOS"]
        self.assertEqual(home["official_out_count"], 1)
        self.assertEqual(home["official_report_capture_status"], "rows_selected")
        self.assertEqual(home["minute_redistribution"]["status"],
                         "conditional_historical_rotation_scenario")
        allocations = home["minute_redistribution"]["conditional"]["allocations"]
        self.assertEqual(allocations["1"], 0)
        self.assertAlmostEqual(sum(allocations.values()), 240)
        self.assertEqual(home["players_without_confirmed_availability"], 5)
        self.assertEqual(home["players_without_historical_minutes"], [])
        self.assertEqual(home["replacement_history_gaps"], [])
        self.assertGreater(home["historical_output_loss_per_game"]["points"], 0)
        self.assertGreater(home["historical_output_from_added_minutes_per_game"]["points"], 0)
        self.assertFalse(result["baseline_probabilities_changed"])
        self.assertFalse(game["probabilities_adjusted"])

    def test_wrong_snapshot_is_rejected(self):
        self.rotation["snapshot_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "another baseline snapshot"):
            build(self.snapshot, self.availability, self.rotation, self.history,
                  "2026-11-10T19:00:00Z")

    def test_post_tipoff_scenario_is_not_created(self):
        result = build(self.snapshot, self.availability, self.rotation, self.history,
                       "2026-11-10T22:01:00Z")
        self.assertEqual(result["games"]["g1"]["status"], "pregame_window_closed")
        self.assertEqual(result["games"]["g1"]["teams"], {})


if __name__ == "__main__":
    unittest.main()
