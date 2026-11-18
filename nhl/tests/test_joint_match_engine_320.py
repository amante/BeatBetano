import copy
import json
import unittest
from pathlib import Path

from nhl.joint_match_engine_320 import run, team_profile


CASE = Path(__file__).resolve().parents[2] / "reports/nhl/integrated-case-COL-CBJ/inputs.json"


class JointMatchEngine320Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(CASE.read_text())

    def test_actual_case_is_four_goalie_scenarios_and_never_published(self):
        out = run(self.inputs)
        self.assertEqual(out["scenario_count"], 4)
        self.assertEqual(out["status"], "historical_reconstruction_only")
        self.assertFalse(out["publishable"])
        self.assertEqual(out["home"], "CBJ")
        self.assertEqual(out["away"], "COL")
        for scenario in out["scenarios"]:
            for side in ("home", "away"):
                markets = scenario["markets"]
                self.assertAlmostEqual(sum(markets["regulation"][k] for k in ("home", "draw", "away")), 1, places=4)
                self.assertAlmostEqual(sum(markets["illustrative_ml"].values()), 1, places=4)

    def test_minute_reallocation_conserves_exact_regulation_budget(self):
        out = run(self.inputs)
        for team in ("CBJ", "COL"):
            minute = out["minute_distribution"][team]
            self.assertAlmostEqual(minute["allocated_minutes"], 300)
            self.assertAlmostEqual(minute["reference_minutes"], 300)
        cbj = out["minute_distribution"]["CBJ"]
        self.assertGreater(cbj["outgoing_minutes"], 0)
        self.assertGreater(cbj["incoming_historical_minutes"], 0)

    def test_all_goalie_pairs_change_rates_without_blending_unconfirmed_starters(self):
        out = run(self.inputs)
        cbj_goal_rates = {round(s["expected_goals"]["home"], 6) for s in out["scenarios"]}
        col_goal_rates = {round(s["expected_goals"]["away"], 6) for s in out["scenarios"]}
        self.assertEqual(len(cbj_goal_rates), 2)
        self.assertEqual(len(col_goal_rates), 2)
        self.assertFalse(any(s["home_goalie"]["starter_confirmed"] or s["away_goalie"]["starter_confirmed"] for s in out["scenarios"]))

    def test_more_opponent_defensive_shots_allowed_changes_goal_rate(self):
        original = run(self.inputs)["scenarios"][0]["expected_goals"]["home"]
        changed = copy.deepcopy(self.inputs)
        changed["teams"]["COL"]["team_summary"]["shotsAgainstPerGame"] += 8
        result = run(changed)["scenarios"][0]["expected_goals"]["home"]
        self.assertGreater(result, original)

    def test_ev_player_production_is_part_of_same_goal_process(self):
        original = run(self.inputs)["scenarios"][0]["expected_goals"]["home"]
        changed = copy.deepcopy(self.inputs)
        player = changed["teams"]["CBJ"]["projected_lines"][0]["players"][0]["production"]
        player["evGoals"] += 10
        player["evPoints"] += 10
        result = run(changed)["scenarios"][0]["expected_goals"]["home"]
        self.assertGreater(result, original)

    def test_pim_exposure_changes_opponent_powerplay_volume(self):
        original = run(self.inputs)["scenarios"][0]["expected_goals"]["home"]
        changed = copy.deepcopy(self.inputs)
        player = changed["teams"]["COL"]["projected_lines"][0]["players"][0]
        player["production"]["penaltyMinutes"] += 20
        result = run(changed)["scenarios"][0]["expected_goals"]["home"]
        self.assertGreater(result, original)

    def test_pk_matchup_changes_powerplay_component(self):
        original = run(self.inputs)["scenarios"][0]["expected_goals"]["home"]
        changed = copy.deepcopy(self.inputs)
        changed["teams"]["COL"]["special_teams"]["opponent_powerplay_goals"] += 4
        result = run(changed)["scenarios"][0]["expected_goals"]["home"]
        self.assertGreater(result, original)

    def test_own_powerplay_conversion_changes_the_same_goal_rate(self):
        original = run(self.inputs)["scenarios"][0]["expected_goals"]["home"]
        changed = copy.deepcopy(self.inputs)
        changed["teams"]["CBJ"]["special_teams"]["powerplay_goals"] += 3
        result = run(changed)["scenarios"][0]["expected_goals"]["home"]
        self.assertGreater(result, original)

    def test_assisted_points_affect_scoring_but_are_converted_to_goal_events(self):
        original = run(self.inputs)
        changed = copy.deepcopy(self.inputs)
        player = changed["teams"]["CBJ"]["projected_lines"][0]["players"][0]["production"]
        player["assists"] += 20
        player["evPoints"] += 20
        result = run(changed)
        self.assertGreater(result["scenarios"][0]["expected_goals"]["home"], original["scenarios"][0]["expected_goals"]["home"])
        original_player = next(p for p in original["lineup_impact"]["CBJ"]["incoming_to_projected_lineup"] if p["name"] == "Dmitri Voronkov")
        self.assertGreaterEqual(original_player["projected_contribution_per_game"]["assists"], 0)

    def test_unresolved_injury_is_blocker_and_scratch_history_is_accounted(self):
        out = run(self.inputs)
        text = " ".join(out["unresolved"])
        self.assertIn("Isac Lundestrom", text)
        scratches = out["lineup_impact"]["CBJ"]["out_of_projection"]
        self.assertIn("Emil Andrae", [p["name"] for p in scratches])

    def test_cutoff_must_be_before_match_start(self):
        changed = copy.deepcopy(self.inputs)
        changed["cutoff_exclusive"] = "2026-11-04"
        with self.assertRaisesRegex(ValueError, "cutoff"):
            run(changed)

    def test_projected_player_team_identity_is_checked(self):
        changed = copy.deepcopy(self.inputs)
        changed["teams"]["CBJ"]["projected_lines"][0]["players"][0]["team_abbrevs"] = "COL"
        with self.assertRaisesRegex(ValueError, "identity"):
            run(changed)

    def test_minute_sum_is_not_overallocated(self):
        cbj = team_profile(self.inputs["teams"]["CBJ"], "CBJ")
        self.assertAlmostEqual(sum(p["projected"]["minutes"] for p in cbj["player_contributions"]), 300)


if __name__ == "__main__":
    unittest.main()
