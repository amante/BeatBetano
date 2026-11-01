import unittest
from nhl.pulso_historical_goalie_join_264 import build

class HistoricalGoalieJoin264(unittest.TestCase):
    def data(self):
        label={"game_id":"1","date":"2026-10-31","home":"BOS","away":"MTL","ml_winner":"home"}
        ob={"game_id":"1","date":"2026-10-31","home":"BOS","away":"MTL",
            "source_verified":True,"feature_as_of_date":"2026-10-30",
            "home_goalie_id":"10","away_goalie_id":"20",
            "home_goalie_prior_sv":"0.92","away_goalie_prior_sv":"0.90",
            "home_team_prior_strength":"0.2","away_team_prior_strength":"-0.1"}
        return label,ob
    def test_valid_join_remains_uncalibrated(self):
        l,o=self.data();r=build([l],[o])
        self.assertEqual(r["eligible_count"],1)
        self.assertFalse(r["calibrated"])
    def test_absent_observation_explicit_blocker(self):
        l,o=self.data();r=build([l],[])
        self.assertEqual(r["blocked_fixtures"][0]["reason"],"no_independent_goalie_observation")
    def test_unverified_source_blocked(self):
        l,o=self.data();o["source_verified"]=False
        self.assertEqual(build([l],[o])["eligible_count"],0)
    def test_same_day_features_blocked(self):
        l,o=self.data();o["feature_as_of_date"]=l["date"]
        self.assertEqual(build([l],[o])["eligible_count"],0)
    def test_fixture_mismatch_rejected(self):
        l,o=self.data();o["away"]="TOR"
        with self.assertRaises(ValueError):build([l],[o])
    def test_unknown_observation_rejected(self):
        l,o=self.data();o["game_id"]="2"
        with self.assertRaises(ValueError):build([l],[o])
    def test_missing_starter_id_blocked(self):
        l,o=self.data();o["home_goalie_id"]=""
        self.assertEqual(build([l],[o])["eligible_count"],0)
if __name__=="__main__":unittest.main()
