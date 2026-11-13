import unittest

from nba.injury_probability import _eligible_out_claims, _eligible_uncertain_claims
from nba.injury_source_reconciliation import normalize_status
from nba.injury_source_fallback import parse_cbs


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

    def test_game_time_decision_is_questionable_and_cbs_out_text_is_parsed(self):
        html = """<table><thead><tr><th>Player</th><th>Position</th><th>Updated</th>
        <th>Injury</th><th>Injury Status</th></tr></thead><tbody>
        <tr><td>Jamal Cain</td><td>SF</td><td>Thu, Nov 12</td><td>Shoulder</td>
        <td>Game Time Decision</td></tr>
        <tr><td>Paolo Banchero</td><td>PF</td><td>Sat, Oct 24</td><td>Ankle</td>
        <td>Expected to be out until at least Nov 22</td></tr></tbody></table>"""
        rows = parse_cbs(html, {}, "2026-11-13T15:00:00+00:00")
        by_player = {row["player_candidate"]: row["status_candidate"] for row in rows}
        self.assertEqual(normalize_status(by_player["Jamal Cain"]), "questionable")
        self.assertEqual(normalize_status(by_player["Paolo Banchero"]), "out")


if __name__ == "__main__":
    unittest.main()
