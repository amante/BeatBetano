import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prospective import generate,settle
class Tests(unittest.TestCase):
    def setup_data(self):
        history=[{"game_id":"h","season":2027,"tipoff_utc":"2026-10-20T23:00:00Z",
                  "home_team":"BOS","away_team":"NYK","home_points":104,"away_points":99}]
        fixtures=[{"game_id":"f","season":2027,"tipoff_utc":"2026-10-24T00:00:00Z",
                   "home_team":"BOS","away_team":"NYK","home_points":None,"away_points":None}]
        return history,fixtures
    def test_generate_and_settle(self):
        h,f=self.setup_data()
        snap=generate(h,f,"2026-10-23T20:00:00Z")
        self.assertEqual(len(snap["predictions"]),1)
        self.assertFalse(snap["predictions"][0]["eligible_for_bet"])
        result=dict(f[0],home_points=110,away_points=90)
        a=settle(snap,[result])
        self.assertEqual(a["settled_games"],1)
        self.assertTrue(0<=a["brier"]["elo"]<=1)
    def test_reject_post_start(self):
        h,f=self.setup_data()
        with self.assertRaisesRegex(ValueError,"already started"):
            generate(h,f,"2026-10-24T01:00:00Z")
    def test_reject_training_leak(self):
        h,f=self.setup_data();h[0]["tipoff_utc"]="2026-10-24T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"Future game"):
            generate(h,f,"2026-10-23T20:00:00Z")
    def test_reject_postgame_fixture(self):
        h,f=self.setup_data();f[0]["home_points"]=100
        with self.assertRaisesRegex(ValueError,"Results forbidden"):
            generate(h,f,"2026-10-23T20:00:00Z")
if __name__=="__main__":unittest.main()
