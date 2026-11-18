import unittest
from unittest.mock import patch

from multisport.certification_holdout import capture


class CertificationHoldoutTests(unittest.TestCase):
    def test_capture_consumes_lineage_warning_return_without_failing(self):
        policy = {
            "frozen_at_utc": "2026-11-01T00:00:00Z",
            "protocol_id": "test-protocol",
            "accepted_model_version_prefixes": {},
            "minimum_settled_forecasts_per_season": 100,
            "minimum_holdout_seasons": 2,
        }
        with patch(
            "multisport.certification_holdout._forecast_chains",
            return_value=([], {}, [], 3),
        ), patch(
            "multisport.certification_holdout._forecast_versions",
            return_value=([], {}),
        ):
            report = capture("unused", policy, {"inputs": {}})
        self.assertEqual(report["inputs"]["legacy_source_output_digest_scope_unverified"], 3)
        self.assertEqual(report["lineage_warnings"], [
            "Legacy source-output sub-digests cannot be independently verified because older snapshots stored a slate digest beside one event payload; enclosing snapshot seals were verified."
        ])
        self.assertFalse(report["certified"])


if __name__ == "__main__":
    unittest.main()
