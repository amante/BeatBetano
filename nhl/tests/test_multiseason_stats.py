import sys,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multiseason_stats import seasons,extract,collect
class Response:
 def __init__(self,rows):self.rows=rows
 def raise_for_status(self):pass
 def json(self):return {"data":self.rows}
class Test(unittest.TestCase):
 def test_season_rollover(self):
  self.assertEqual(seasons(date(2026,10,27),5)[0],"20262027")
  self.assertEqual(seasons(date(2026,1,10),1),["20252026"])
 def test_current_season_rows(self):
  urls=[]
  def fetch(url):
   urls.append(url)
   return Response([{"playerId":1,"gamesPlayed":3}]) 
  rows=extract(fetch,"20262027","skater/summary")
  self.assertEqual(len(rows),1)
  self.assertIn("seasonId%3D20262027",urls[0])
 def test_multi_team_stints_are_preserved(self):
  calls=[]
  def fetch(url):
   calls.append(url)
   return Response([
    {"playerId":99,"teamId":1,"gamesPlayed":4},
    {"playerId":99,"teamId":2,"gamesPlayed":6},
    {"playerId":99,"teamId":2,"gamesPlayed":6},
   ]) if len(calls)==1 else Response([])
  rows=extract(fetch,"20262027","skater/summary",limit=3)
  self.assertEqual(len(rows),2)
  self.assertEqual({r["teamId"] for r in rows},{1,2})
 def test_exact_duplicate_does_not_erase_valid_rows(self):
  rows=extract(lambda url:Response([
    {"playerId":1,"teamId":1},
    {"playerId":1,"teamId":1},
    {"playerId":2,"teamId":3}]),"20262027","skater/summary",limit=100)
  self.assertEqual(len(rows),2)
 def test_empty_not_silent(self):
  r=collect(lambda url:Response([]),date(2026,10,27),1)
  self.assertEqual(r["reports"]["20262027"]["skater/summary"]["status"],"empty")
  self.assertFalse(r["historical_backtest_eligible"])
if __name__=="__main__":unittest.main()
