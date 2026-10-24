import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from daily_pipeline import run

class Tests(unittest.TestCase):
    def setup(self):
        historical=[{"game_id":"prev","season":2027,"tipoff_utc":"2026-10-22T00:00:00Z",
            "home_team":"BOS","away_team":"NYK","home_points":101,"away_points":100}]
        fixture={"game_id":"next","season":2027,"tipoff_utc":"2026-10-24T01:00:00Z",
            "home_team":"NYK","away_team":"BOS","home_points":None,"away_points":None}
        feed={"as_of_utc":"2026-10-23T22:00:00Z","future_fixtures":[fixture],
            "source":"mocked ESPN scoreboard"}
        return historical,feed
    def test_generates_three_model_pregame_snapshot(self):
        h,f=self.setup()
        r=run(h,f,"2026-10-23T22:02:00Z")
        self.assertEqual(len(r["predictions"]),1)
        self.assertTrue(all(k in r["predictions"][0] for k in ("elo_p_home","challenger_p_home","hybrid_p_home")))
        self.assertFalse(r["predictions"][0]["eligible_for_bet"])
    def test_rejects_stale_feed(self):
        h,f=self.setup()
        with self.assertRaisesRegex(ValueError,"older than five minutes"):
            run(h,f,"2026-10-23T22:07:00Z")
    def test_no_future_fixtures(self):
        h,f=self.setup();f["future_fixtures"]=[]
        with self.assertRaisesRegex(ValueError,"No not-yet-started"):
            run(h,f,"2026-10-23T22:01:00Z")
if __name__=="__main__":unittest.main()
