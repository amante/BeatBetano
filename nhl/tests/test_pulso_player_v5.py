import unittest
from nhl.pulso_player_v5 import blend,season_of,select_weights,bins,evaluate
from nhl.pulso_player_v1 import validate
class TestV5(unittest.TestCase):
 def test_season_and_blend(self):
  self.assertEqual(season_of("2026-03-01"),"20252026")
  self.assertEqual(season_of("2026-10-01"),"20262027")
  self.assertEqual(blend(10,20,.25),12.5)
 def test_weights_use_training_only(self):
  train=[{"predictions":{"recent10":{"toi_minutes":10},"contextual":{"toi_minutes":20}},"actual":{"toi_minutes":10}}]
  self.assertEqual(select_weights(train,"toi_minutes"),0)
  self.assertEqual(select_weights([],"toi_minutes"),.5)
 def test_no_same_day_in_target(self):
  rows=[]
  from datetime import date,timedelta
  for i in range(30):
   d=(date(2025,9,1)+timedelta(days=i)).isoformat()
   rows.append({"game_id":str(i),"date":d,"player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":10,"shots_on_goal":2,"goals":0})
  rows.append({"game_id":"30","date":"2025-10-01","player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":30,"shots_on_goal":10,"goals":3})
  result,weights=evaluate(validate(rows),{"97":"C"},"2025-10-01")
  self.assertEqual(len(result),1)
  self.assertLess(result[0]["predictions"]["hybrid"]["shots_on_goal"],5)
  self.assertLess(result[0]["predictions"]["hybrid"]["goals"],1)
if __name__=="__main__":unittest.main()
