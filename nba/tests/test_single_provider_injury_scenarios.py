import unittest

from nba.injury_probability import _eligible_out_claims, _eligible_uncertain_claims
from nba.injury_source_reconciliation import normalize_status
from nba.injury_status_text import extract_status_candidate


class TrustedProviderInjuryScenarioTests(unittest.TestCase):
    def claim(self, source, status):
        return {"source": source, "source_type": "provider_injury_report",
                "status": status, "officially_verified": False,
                "editorial_claim": False}

    def test_single_cbs_out_claim_can_enter_research_scenario(self):
        player = {"player_id": "p1", "player": "Paolo Banchero",
                  "status_agreement": "out", "conflict": False,
                  "claims": [self.claim("CBS Sports", "out")]}
        accepted, unresolved = _eligible_out_claims([player])
        self.assertEqual(unresolved, [])
        self.assertEqual(accepted[0]["accepted_source_class"], "single_provider_research_claim")

    def test_status_conflict_stays_unresolved(self):
        player = {"player_id": "p1", "player": "Jalen Suggs",
                  "status_agreement": None, "conflict": True,
                  "claims": [self.claim("CBS Sports", "questionable"),
                             self.claim("ESPN", "out")]}
        accepted, unresolved = _eligible_out_claims([player])
        self.assertEqual(accepted, [])
        self.assertEqual(unresolved[0]["reason"], "source_status_conflict")

    def test_single_source_questionable_remains_unweighted_conditional(self):
        player = {"player_id": "p2", "player": "Jamal Cain",
                  "status_agreement": "questionable", "conflict": False,
                  "claims": [self.claim("CBS Sports", "questionable")]}
        accepted, unresolved = _eligible_uncertain_claims([player])
        self.assertEqual(unresolved, [])
        self.assertEqual(accepted[0]["scenario_status"], "questionable")
        self.assertEqual(accepted[0]["accepted_source_class"], "single_provider_conditional_claim")

    def test_game_time_decision_and_expected_out_text_are_parsed(self):
        game_time = extract_status_candidate("Game Time Decision")
        expected_out = extract_status_candidate("Expected to be out until at least Nov 22")
        self.assertEqual(normalize_status(game_time), "questionable")
        self.assertEqual(normalize_status(expected_out), "out")
        self.assertIsNone(extract_status_candidate("No injury update"))


if __name__ == "__main__":
    unittest.main()
