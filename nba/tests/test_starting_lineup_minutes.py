import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starting_lineup_minutes import apply_role_weights, estimate, resolve_starter_ids
from official_injury_impact import _allocations


class StartingLineupMinuteTests(unittest.TestCase):
    def setUp(self):
        self.roster = {"lineup_status": "projected",
                       "players": [{"player_id": str(i), "player": f"P{i}",
                                    "starter_projected": True,
                                    "position_abbreviation": "G" if i < 2 else "F"}
                                   for i in range(5)]}
        self.lineup = {"lineup_status": "projected",
                       "source_url": "https://www.rotowire.com/basketball/nba-lineups.php",
                       "observed_at_utc": "2026-11-10T18:00:00Z",
                       "starters": [f"P{i}" for i in range(5)]}
        self.emitted = "2026-11-10T19:00:00Z"
        self.tipoff = "2026-11-10T23:00:00Z"
        self.history = [{"player_id": str(i), "team": "BOS", "starter_reported_postgame": True,
                         "tipoff_utc": f"2026-11-0{d}T20:00:00Z",
                         "observed_at_utc": f"2026-11-0{d+1}T01:00:00Z",
                         "minutes_played": 30+i, "did_not_play": False}
                        for i in range(5) for d in (1, 2)]

    def test_uses_pre_tip_roto_wire_five_and_prior_starter_minutes(self):
        result = estimate("BOS", self.roster, self.lineup, self.history, self.emitted, self.tipoff)
        self.assertEqual(result["status"], "role_weights_ready")
        self.assertEqual(len(result["weights"]), 5)
        self.assertEqual(result["weights"]["0"], 30.0)

    def test_rejects_lineup_observed_after_tipoff(self):
        lineup = dict(self.lineup, observed_at_utc="2026-11-11T00:00:00Z")
        result = estimate("BOS", self.roster, lineup, self.history, self.emitted, self.tipoff)
        self.assertEqual(result["status"], "lineup_not_observed_before_issue_and_tipoff")

    def test_requires_all_five_players_to_have_historical_starts(self):
        result = estimate("BOS", self.roster, self.lineup, self.history[:-1], self.emitted, self.tipoff)
        self.assertEqual(result["status"], "insufficient_historical_starter_minutes")
        self.assertEqual(result["weights"], {})

    def test_roto_wire_initials_resolve_only_to_unique_roster_players(self):
        members = [{"player_id": "1", "player": "Keyonte George"},
                   {"player_id": "2", "player": "Klay Thompson"},
                   {"player_id": "3", "player": "A Player"},
                   {"player_id": "4", "player": "B Player"},
                   {"player_id": "5", "player": "C Player"}]
        names = ["K. George", "K. Thompson", "A Player", "B Player", "C Player"]
        self.assertEqual(resolve_starter_ids(members, names), ["1", "2", "3", "4", "5"])
        ambiguous = members + [{"player_id": "6", "player": "Kendrick George"}]
        self.assertEqual(resolve_starter_ids(ambiguous, names), [])

    def test_role_minutes_replace_generic_weights_in_the_allocation_input(self):
        samples = {"1": {"player_id": "1", "minutes_projection": 30.0}}
        evidence = {"weights": {"1": 38.5},
                    "players": [{"player_id": "1", "player": "P1", "position": "G"}]}
        applied = apply_role_weights(samples, evidence)
        self.assertEqual(applied, ["1"])
        self.assertEqual(samples["1"]["minutes_projection"], 38.5)
        self.assertTrue(samples["1"]["lineup_role_weight_applied"])

    def test_starter_role_weight_changes_replacement_minute_allocation(self):
        rotation = {"provisional_rotation": [
            {"player_id": str(i), "player": f"P{i}", "minutes_projection": 30.0,
             "sample_games": 5, "projection_method": "mean_last_five_observed_minutes"}
            for i in range(7)]}
        evidence = {"status": "role_weights_ready", "weights": {"0": 45.0},
                    "players": [{"player_id": "0", "player": "P0", "position": "G"}]}
        result = _allocations("BOS", rotation, {"6"}, {}, [{"player_id": "6", "player": "P6"}], evidence)
        self.assertEqual(result["status"], "conditional_historical_rotation_scenario")
        self.assertEqual(result["lineup_role_weights_applied"], 1)
        allocation = result["conditional"]["allocations"]
        self.assertGreater(allocation["0"], allocation["1"])



if __name__ == "__main__":
    unittest.main()
