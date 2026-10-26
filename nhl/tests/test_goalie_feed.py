import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_feed import candidate_logs
def payload(_):
 return {"gameLog":[{"gameDate":"2026-10-20","gameType":2,"shotsAgainst":30,"saves":28},
 {"gameDate":"2026-10-27","gameType":2,"shotsAgainst":20,"saves":20}]}
class Test(unittest.TestCase):
 def test_pregame_only(self):
  out=candidate_logs({"goalies":[{"id":44}]},payload,"BOS","2026-10-26T15:00:00Z","2026-10-27T00:00:00Z",20262027)[0]
  self.assertEqual(out["shots_against"],30)
  self.assertEqual(out["saves"],28)
  self.assertEqual(out["starter_status"],"unknown")
  self.assertIsNone(out["gsax"])
 def test_missing_goalies(self):
  self.assertEqual(candidate_logs({},payload,"BOS","2026-10-26T15:00:00Z","2026-10-27T00:00:00Z",20262027),[])
if __name__=="__main__":unittest.main()
