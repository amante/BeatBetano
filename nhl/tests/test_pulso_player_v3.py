import unittest
from nhl.pulso_player_v3 import roster_ids,schedule_rest,evaluate
from nhl.pulso_player_v1 import validate
class V3Tests(unittest.TestCase):
 def test_roster(self):
  f=lambda url:{"forwards":[{"id":97,"positionCode":"C"}],"defensemen":[{"id":2,"positionCode":"D"}]}
  x=roster_ids("EDM","20252026",f)
  self.assertEqual(set(x),{"97","2"})
 def test_team_rest_including_missed_appearance(self):
  def f(url):return {"games":[{"id":1,"gameType":2,"gameDate":"2026-10-01"},{"id":2,"gameType":2,"gameDate":"2026-10-02"},{"id":3,"gameType":2,"gameDate":"2026-10-04"}]}
  result,_=schedule_rest("EDM","20262027",f)
  self.assertIsNone(result["1"][0])
  self.assertEqual(result["2"][0],0)
  self.assertEqual(result["3"][0],1)
 def test_no_invented_predictions_when_short(self):
  r=validate([{"game_id":"1","date":"2026-10-01","player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":20,"shots_on_goal":3,"goals":0}])
  result=evaluate(r,{"97":"C"},start="2026-10-01")
  self.assertEqual(result["observations"],0)
if __name__=="__main__":unittest.main()
