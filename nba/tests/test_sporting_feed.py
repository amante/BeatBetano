import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sporting_feed import extract

class Tests(unittest.TestCase):
    def test_extract_supplementary_and_never_claim_official(self):
        snap={"predictions":[{"game_id":"10","home_team":"BOS","away_team":"NYK"}]}
        feed={"injuries":[{"team":{"abbreviation":"BOS"},"injuries":[
          {"athlete":{"displayName":"Example Player"},"status":"Out","details":{"detail":"Knee"}}]},
          {"team":{"abbreviation":"LAL"},"injuries":[{"athlete":{"displayName":"Not this game"},"status":"Out"}]}]}
        out=extract(feed,snap,"2026-10-25T18:00:00+00:00")
        g=out["games"]["10"]
        self.assertEqual(len(g["supplementary_injury_observations"]["items"]),1)
        self.assertFalse(g["supplementary_injury_observations"]["source_verified_official"])
        self.assertFalse(g["complete_pregame"])
    def test_malformed_feed_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"injuries array"):
            extract({"events":[]},{"predictions":[]},"2026-10-25T18:00:00Z")
if __name__=="__main__":unittest.main()
