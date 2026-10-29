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
 def test_missing_season_is_not_fabricated(self):
  from nhl.pulso_player_v3 import build
  def fake(url):
   if "/roster/" in url:return {"forwards":[{"id":97,"positionCode":"C"}],"defensemen":[]}
   if "/club-schedule-season/" in url:return {"games":[{"id":1,"gameType":2,"gameDate":"2026-10-01"},{"id":2,"gameType":2,"gameDate":"2026-10-04"}]}
   return {"playerId":97,"seasonId":20262027,"gameLog":None}
  rows,positions,sources=build(("EDM",),("20262027",),fake)
  self.assertEqual(rows,[])
  self.assertTrue(any(x.get("empty") for x in sources if x["kind"]=="player_log"))
 def test_provider_error_does_not_count_as_no_games(self):
  from nhl.pulso_player_v3 import build
  def fake(url):
   if "/roster/" in url:return {"forwards":[{"id":97,"positionCode":"C"}],"defensemen":[]}
   if "/club-schedule-season/" in url:return {"games":[]}
   return {"error":"upstream unavailable"}
  with self.assertRaises(ValueError):build(("EDM",),("20262027",),fake)
 def test_invalid_record_reports_exact_player_game(self):
  bad={"game_id":"2026020001","date":"2026-10-01","player_id":"8470000","team":"EDM","opponent":"LAK","home":True,"rest_days":0,"toi_minutes":20,"shots_on_goal":0,"goals":1}
  with self.assertRaisesRegex(ValueError,"player=8470000 game=2026020001") as e:
   validate([bad])
  self.assertIn("sog=0",str(e.exception))
  self.assertIn("goals=1",str(e.exception))
if __name__=="__main__":unittest.main()
