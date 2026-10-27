import sys,unittest
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_delta import delta,identity,index
from multiseason_stats import seasons
class Tests(unittest.TestCase):
 def test_current_season(self):
  self.assertEqual(seasons(date(2026,10,27),1),["20262027"])
 def test_added_changed_missing(self):
  def snapshot(skaters):
   return {"season":"20262027","as_of_utc":"2026-10-27T12:00:00Z","reports":{
    "skater/summary":skaters,
    "goalie/summary":[{"playerId":3,"teamId":9,"saves":200}],
    "team/summary":[{"teamId":9,"gamesPlayed":8}]}}
  old=snapshot([{"playerId":1,"teamId":9,"points":2},{"playerId":2,"teamId":9,"points":3}])
  new=snapshot([{"playerId":1,"teamId":9,"points":5},{"playerId":4,"teamId":9,"points":1}])
  row=delta(old,new)["reports"]["skater/summary"]
  self.assertEqual((row["added_count"],row["updated_count"],row["missing_count"]),(1,1,1))
 def test_stint_ids(self):
  rows=[{"playerId":5,"teamId":1},{"playerId":5,"teamId":2}]
  self.assertEqual(len(index("skater/summary",rows)),2)
 def test_missing_baseline(self):
  current={"season":"20262027","as_of_utc":"2026-10-27T12:00:00Z",
   "reports":{k:[{"playerId":1,"teamId":3}] if k!="team/summary" else [{"teamId":3}] for k in ("skater/summary","goalie/summary","team/summary")}}
  self.assertTrue(delta(None,current)["baseline_missing"])
if __name__=="__main__":unittest.main()
