import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from walkforward_calibration import parse_games,fetch_season,predict,scores,calibrate
from datetime import date
class Response:
 def raise_for_status(self):pass
 def json(self):return {"gameWeek":[{"date":"2025-01-01","games":[
  {"id":123,"gameType":2,"gameState":"OFF",
  "homeTeam":{"abbrev":"BOS","score":3},"awayTeam":{"abbrev":"MTL","score":2}}]}]}
class Tests(unittest.TestCase):
 def test_weekly_fetch_one_request(self):
  urls=[]
  def fetch(url):urls.append(url);return Response()
  rows,errors=fetch_season(fetch,date(2025,1,1),date(2025,1,2))
  self.assertEqual((len(rows),len(errors),len(urls)),(1,0,1))
 def test_same_day_no_leakage(self):
  history=[{"date":"2025-01-01","id":str(i),"home":"BOS","away":"MTL","hg":3,"ag":2} for i in range(151)]
  target={"date":"2025-01-02","id":"a","home":"BOS","away":"MTL","hg":2,"ag":1}
  a=scores(history+[target],(3.,.08,10),150)
  flipped=dict(target,hg=1,ag=2)
  b=scores(history+[flipped],(3.,.08,10),150)
  self.assertAlmostEqual(a["predictions"][0]["p"],b["predictions"][0]["p"])
 def test_train_test_overlap(self):
  with self.assertRaises(ValueError):calibrate([], "2025-10-01","2025-09-01")
if __name__=="__main__":unittest.main()
