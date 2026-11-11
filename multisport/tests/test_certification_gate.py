import unittest
from copy import deepcopy

from multisport.certification_gate import assess


def packet():
    rows = []
    # Deterministic, paired outcomes across two held-out seasons. Values make the
    # challenger strictly better than baseline and its required ablation.
    for season, year in ((2024, 2024), (2025, 2025)):
        for index in range(100):
            outcome = index % 2
            rows.append({
                "event_id": f"{year}-{index}",
                "season": season,
                "prediction_as_of_utc": f"{year}-01-01T12:00:00Z",
                "outcome": outcome,
                "probabilities": {
                    "baseline": 0.5,
                    "challenger": 0.9 if outcome else 0.1,
                    "without_lineups": 0.5,
                },
            })
    return {
        "scope": {"sport": "nba", "market": "moneyline", "model_version": "candidate-v1",
                  "model_code_sha256": "c" * 64},
        "protocol": {
            "holdout_seasons": [2024, 2025],
            "min_games_per_season": 100,
            "locked_at_utc": "2023-12-01T00:00:00Z",
            "first_holdout_prediction_utc": "2024-01-01T12:00:00Z",
            "required_ablations": ["without_lineups"],
        },
        "lineage": {
            "forecast_archive_sha256": "a" * 64,
            "training_data_manifest_sha256": "b" * 64,
            "model_code_revision": "1234567890abcdef",
            "model_code_sha256": "c" * 64,
        },
        "walk_forward_rows": rows,
        "independent_review": {
            "reviewer_id": "independent-reviewer",
            "evidence_ref": "reports/review-1",
            "reviewed_at_utc": "2026-01-01T00:00:00Z",
            "source_authenticity_verified": True,
            "lineage_verified": True,
            "temporal_leakage_reviewed": True,
            "reliability_reviewed": True,
        },
    }


class CertificationGateTests(unittest.TestCase):
    def test_complete_evidence_is_eligible_for_review_but_never_certified(self):
        result = assess(packet())
        self.assertTrue(result["eligible_for_certification_review"])
        self.assertFalse(result["certified"])
        self.assertFalse(result["automatic_promotion_allowed"])

    def test_policy_must_be_frozen_before_holdout(self):
        evidence = packet()
        evidence["protocol"]["locked_at_utc"] = "2024-01-02T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "before"):
            assess(evidence)

    def test_missing_lineage_digest_fails_closed(self):
        evidence = packet()
        evidence["lineage"]["training_data_manifest_sha256"] = None
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            assess(evidence)

    def test_small_or_incomplete_holdout_is_not_eligible(self):
        evidence = packet()
        evidence["walk_forward_rows"] = evidence["walk_forward_rows"][:-1]
        result = assess(evidence)
        self.assertFalse(result["eligible_for_certification_review"])
        self.assertIn("insufficient_games:2025", result["reasons"])

    def test_review_attestation_is_required(self):
        evidence = packet()
        evidence["independent_review"]["lineage_verified"] = False
        result = assess(evidence)
        self.assertFalse(result["eligible_for_certification_review"])
        self.assertIn("independent_review_incomplete", result["reasons"])

    def test_rows_from_unregistered_season_are_rejected(self):
        evidence = packet()
        evidence["walk_forward_rows"][0]["season"] = 2023
        with self.assertRaisesRegex(ValueError, "outside"):
            assess(evidence)


if __name__ == "__main__":
    unittest.main()
