import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_players import capture,measure,summary
class Tests(unittest.TestCase):
 def test_roster_intersection_is_real_not_line_assignment(self):
  roster={"forwards":[{"id":1,"firstName":{"default":"Ana"},"lastName":{"default":"One"},"positionCode":"C"}],"defensemen":[]}
  stats={"skaters":[{"playerId":1,"gamesPlayed":5,"points":6,"goals":2,"assists":4},{"playerId":2,"gamesPlayed":3,"points":12}]}
  x=measure(roster,stats,"BOS","2026-10-27T10:00:00Z")
  self.assertEqual(len(x["skaters"]),1)
  self.assertEqual(x["skaters"][0]["points_per_game"],1.2)
  self.assertFalse(x["confirmed_lineup"])
  self.assertIsNone(x["crs"])
 def test_future_only_and_summary(self):
  slate={"sport":"nhl","as_of_utc":"2026-10-27T10:00:00Z","events":[{"start_utc":"2026-10-28T00:00:00Z","home_team":"BOS","away_team":"MTL"}]}
  def fetch(url):return {"forwards":[],"defensemen":[]} if "/roster/" in url else {"skaters":[]}
  def forbidden(url):
   if "/roster/" in url:raise AssertionError("duplicate roster fetch")
   return {"skaters":[]}
  roster={"forwards":[{"id":10,"positionCode":"C"}],"defensemen":[]}
  result=capture(slate,forbidden,{"BOS":roster,"MTL":roster})
  self.assertEqual(len(result["teams"]),2)
  self.assertEqual(result["teams"]["BOS"]["roster_forwards"],1)
  self.assertTrue(result["teams"]["BOS"]["roster_reused"])
  self.assertIn("MTL",summary(result))
  slate["events"][0]["start_utc"]="2026-10-27T09:00:00Z"
  with self.assertRaises(ValueError):capture(slate,fetch)
if __name__=="__main__":unittest.main()
