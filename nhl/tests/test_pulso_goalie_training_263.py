import unittest
from nhl.pulso_goalie_training_263 import audit

def row(i,day="2026-10-30",feature_day="2026-10-29"):
    return {"game_id":str(i),"date":day,"feature_as_of_date":feature_day,
            "home":"BOS","away":"MTL","home_goalie_id":"1","away_goalie_id":"2",
            "ml_winner":"home","home_goalie_prior_sv":"0.92",
            "away_goalie_prior_sv":"0.90","home_team_prior_strength":"0.1",
            "away_team_prior_strength":"-0.1"}
class GoalieTraining263(unittest.TestCase):
    def test_reject_same_day_leakage(self):
        with self.assertRaises(ValueError):audit([row(1,feature_day="2026-10-30")])
    def test_reject_missing_goalie_identity(self):
        r=row(1);r["away_goalie_id"]=""
        with self.assertRaises(ValueError):audit([r])
    def test_reject_missing_prior_feature(self):
        r=row(1);r["home_goalie_prior_sv"]=""
        with self.assertRaises(ValueError):audit([r])
    def test_reject_duplicate_fixture(self):
        with self.assertRaises(ValueError):audit([row(1),row(1)])
    def test_reject_invalid_feature(self):
        r=row(1);r["home_goalie_prior_sv"]="1.2"
        with self.assertRaises(ValueError):audit([r])
    def test_not_ready_with_one_day(self):
        self.assertEqual(audit([row(1)])["status"],"blocked_insufficient_historical_dates")
    def test_strict_chronological_splits(self):
        from datetime import date,timedelta
        data=[]
        for i in range(15):
            day=date(2026,10,1)+timedelta(days=i)
            for j in range(20):
                data.append(row(i*20+j,day.isoformat(),(day-timedelta(days=1)).isoformat()))
        out=audit(data,minimum_train=60,minimum_holdout=20)
        self.assertEqual(out["status"],"eligible_for_fitting")
        self.assertEqual(out["training_rows"],300)
        self.assertTrue(out["fit_through"] < out["validation_through"])
        self.assertFalse(out["validated_model"])
if __name__=="__main__":unittest.main()
