import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pregame_snapshot import join
class TestPregameCache(unittest.TestCase):
 def slate(self,asof="2026-10-27T22:00:00Z"):
  return {"sport":"nhl","as_of_utc":asof,"events":[{"event_id":"1","home_team":"PHI","away_team":"CBJ","start_utc":"2026-10-28T00:00:00Z"}]}
 def snapshot(self,stamp="2026-10-27T21:00:00Z"):
  return {"sport":"nhl","season":"20262027","as_of_utc":stamp,
    "reports":{"skater/summary":[{"playerId":1,"teamAbbrevs":"PHI","positionCode":"C","points":1}],
     "goalie/summary":[{"playerId":2,"teamAbbrevs":"CBJ"}],
     "team/summary":[{"teamFullName":"Philadelphia Flyers","teamId":4}]*16+[{"teamFullName":"Columbus Blue Jackets","teamId":29}]*16}}
 def test_future_snapshot_rejected(self):
  with self.assertRaisesRegex(ValueError,"future"):join(self.slate(),self.snapshot("2026-10-27T23:00:00Z"))
 def test_stale_rejected(self):
  with self.assertRaisesRegex(ValueError,"stale"):join(self.slate(),self.snapshot("2026-10-26T00:00:00Z"))
 def test_observed_only(self):
  result=join(self.slate(),self.snapshot())
  self.assertEqual(len(result["games"]),1)
  self.assertIsNone(result["games"][0]["official_ml"])
  self.assertFalse(result["calibrated"])
if __name__=="__main__":unittest.main()
