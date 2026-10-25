import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from availability_impact import build

class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"content_sha256":"abc",
                         "created_at_utc":"2026-10-25T17:00:00Z",
                         "predictions":[{"game_id":"1","tipoff_utc":"2026-10-25T20:00:00Z",
                                         "home_team":"BOS","away_team":"NYK"}]}
        team = {"source_observed_at_utc":"2026-10-25T16:30:00Z",
                "lineup_verified":True,"rotation_verified":True,
                "official_injury_report_verified":True,
                "confirmed_starters":["a","b","c","d","e"],
                "bench_rotation":[{"player":"f","expected_minutes":20}],
                "official_injuries":[{"player":"g","status":"Out"}]}
        self.roster = {"snapshot_sha256":"abc",
                       "games":{"1":{"home":dict(team),"away":dict(team),
                                     "positional_matchups_verified":True}}}

    def test_verified_features_never_make_final_adjustment(self):
        row = build(self.snapshot,self.roster)["games"]["1"]
        self.assertTrue(row["feature_complete"])
        self.assertEqual(row["home_features"]["injury_counts"]["out"],1)
        self.assertIsNone(row["candidate_log_odds_delta"])

    def test_future_observation_rejected(self):
        self.roster["games"]["1"]["home"]["source_observed_at_utc"]="2026-10-25T18:00:00Z"
        row = build(self.snapshot,self.roster)["games"]["1"]
        self.assertFalse(row["feature_complete"])

    def test_missing_verified_team_fails_closed(self):
        self.roster["games"]["1"]["away"]["official_injury_report_verified"]=False
        self.assertFalse(build(self.snapshot,self.roster)["games"]["1"]["feature_complete"])

    def test_wrong_snapshot_rejected(self):
        self.roster["snapshot_sha256"]="wrong"
        with self.assertRaises(ValueError):
            build(self.snapshot,self.roster)

if __name__ == "__main__":
    unittest.main()
