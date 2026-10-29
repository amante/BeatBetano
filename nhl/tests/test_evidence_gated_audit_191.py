import unittest
from nhl.evidence_gated_audit_191 import validate_manifest

LABELS = [{"game_id": "1", "date": "2026-10-10"}]

def feature(recorded="2026-10-09T12:00:00Z", **kwargs):
    return {"source": "dated-external-record", "recorded_at": recorded, **kwargs}

class Evidence191Tests(unittest.TestCase):
    def test_missing_data_not_zero_or_effect(self):
        result = validate_manifest([], LABELS)
        self.assertEqual(result["special_teams"]["verified_n"], 0)
        self.assertIsNone(result["availability_delta"]["predictive_effect"])

    def test_future_and_same_day_excluded(self):
        row = {"game_id": "1", "target_date": "2026-10-10",
               "modules": {"fatigue": feature("2026-10-10T01:00:00Z", rest_differential=2)}}
        self.assertEqual(validate_manifest([row], LABELS)["fatigue"]["verified_n"], 0)

    def test_prior_date_is_counted(self):
        row = {"game_id": "1", "target_date": "2026-10-10",
               "modules": {"fatigue": feature(rest_differential=0),
                           "division_rivalry": feature(division=False, rivalry_tier=None)}}
        report = validate_manifest([row], LABELS)
        self.assertEqual(report["fatigue"]["verified_n"], 1)
        self.assertEqual(report["division_rivalry"]["verified_n"], 0)

    def test_availability_requires_both_sources(self):
        row = {"game_id": "1", "target_date": "2026-10-10",
               "modules": {"availability_delta": feature(home_roster_delta=0.1, away_roster_delta=-0.1)}}
        self.assertEqual(validate_manifest([row], LABELS)["availability_delta"]["verified_n"], 0)

    def test_duplicate_rejected(self):
        row = {"game_id": "1", "target_date": "2026-10-10"}
        with self.assertRaises(ValueError):
            validate_manifest([row, row], LABELS)

    def test_naive_timestamp_rejected(self):
        row = {"game_id": "1", "target_date": "2026-10-10",
               "modules": {"fatigue": feature("2026-10-09T12:00:00", rest_differential=1)}}
        with self.assertRaises(ValueError):
            validate_manifest([row], LABELS)

if __name__ == "__main__":
    unittest.main()
