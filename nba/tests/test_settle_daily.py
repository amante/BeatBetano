import hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from settle_daily import report,verify_snapshot
class Tests(unittest.TestCase):
    def fixture(self):
        snap={"created_at_utc":"2026-10-25T20:00:00+00:00",
              "predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK",
                  "tipoff_utc":"2026-10-26T01:00:00Z",
                  "elo_p_home":.6,"challenger_p_home":.65,"hybrid_p_home":.6}]}
        snap["content_sha256"]=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        game={"game_id":"1","home_team":"BOS","away_team":"NYK",
              "tipoff_utc":"2026-10-26T01:00:00Z","home_points":110,"away_points":98}
        return snap,game
    def test_completed_postmortem(self):
        snap,g=self.fixture();r=report(snap,[g])
        self.assertTrue(r["complete"])
        self.assertAlmostEqual(r["brier"]["elo"],.16)
        self.assertEqual(r["unsettled_games"],0)
    def test_partial_does_not_claim_complete(self):
        snap,_=self.fixture();r=report(snap,[])
        self.assertFalse(r["complete"])
        self.assertEqual(r["settled_games"],0)
    def test_snapshot_tampering_rejected(self):
        snap,g=self.fixture();snap["predictions"][0]["elo_p_home"]=.9
        with self.assertRaisesRegex(ValueError,"digest mismatch"):report(snap,[g])
if __name__=="__main__":unittest.main()
