import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from roster_matchups import evaluate
class Tests(unittest.TestCase):
    def snap(self):
        return {"created_at_utc":"2026-10-25T18:00:00Z","content_sha256":"x",
            "predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-25T22:00:00Z"}]}
    def test_missing_data_not_verified(self):
        g=evaluate(self.snap())["games"]["1"]
        self.assertFalse(g["availability_review_complete"])
        self.assertFalse(g["home"]["lineup_verified"])
        self.assertIsNone(g["quantified_log_odds_adjustment"])
    def test_supplemental_injury_not_official(self):
        s={"games":{"1":{"supplementary_injury_observations":{"items":[{"player":"X","status":"Out"}]}}}}
        g=evaluate(self.snap(),s)["games"]["1"]
        self.assertEqual(len(g["supplementary_injuries"]["items"]),1)
        self.assertFalse(g["home"]["official_injury_report_verified"])
    def test_stale_inputs_fail_closed(self):
        team={"lineup_confirmed":True,"confirmed_starters":["a","b","c","d","e"],
            "lineup_source":"official","source_observed_at_utc":"2026-10-25T23:00:00Z"}
        g=evaluate(self.snap(),verified={"games":{"1":{"home":team}}})["games"]["1"]
        self.assertFalse(g["home"]["lineup_verified"])
if __name__=="__main__":unittest.main()
