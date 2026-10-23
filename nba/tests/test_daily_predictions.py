import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from daily_predictions import predict
class Tests(unittest.TestCase):
    def rows(self):
        h=[{"game_id":"old","season":2026,"tipoff_utc":"2026-04-01T20:00:00Z",
            "home_team":"BOS","away_team":"NYK","home_points":108,"away_points":98}]
        f=[{"game_id":"future","season":2027,"tipoff_utc":"2026-10-23T23:00:00Z",
            "home_team":"BOS","away_team":"NYK","home_points":None,"away_points":None}]
        return h,f
    def test_valid_pregame(self):
        h,f=self.rows()
        result=predict(h,f,"2026-10-23")
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(result[0]["p_away"]+result[0]["p_home"],1,places=5)
        self.assertFalse(result[0]["validated_calibration"])
    def test_futures_cannot_train(self):
        h,f=self.rows();h[0]["tipoff_utc"]="2026-10-23T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"at/after"):
            predict(h,f,"2026-10-23")
    def test_postgame_results_cannot_enter_fixtures(self):
        h,f=self.rows();f[0]["home_points"]=99
        with self.assertRaisesRegex(ValueError,"Refuse game results"):
            predict(h,f,"2026-10-23")
    def test_fixture_date_validated(self):
        h,f=self.rows();f[0]["tipoff_utc"]="2026-10-24T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"outside requested"):
            predict(h,f,"2026-10-23")
if __name__=="__main__":unittest.main()
