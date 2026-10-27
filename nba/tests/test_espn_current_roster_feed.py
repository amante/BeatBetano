import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from espn_current_roster_feed import extract_teams,extract_roster,collect
class Response:
 def __init__(self,v):self.v=v
 def raise_for_status(self):pass
 def json(self):return self.v
class Session:
 def get(self,url,**kwargs):
  if url.endswith("/teams"):return Response({"sports":[{"leagues":[{"teams":[{"team":{"abbreviation":"OKC","id":"25"}},{"team":{"abbreviation":"PHX","id":"21"}}]}]}]})
  return Response({"athletes":[{"id":str(i),"displayName":"Player "+str(i)} for i in range(7)]})
class Tests(unittest.TestCase):
 def test_normalized(self):
  x=extract_roster({"athletes":[{"items":[{"id":"1","displayName":"One"}]}]})
  self.assertEqual(x,[{"player_id":"1","player":"One"}])
 def test_roster_not_availability(self):
  s={"content_sha256":"h","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX"}]}
  r=collect(s,Session(),"2026-10-26T22:00:00Z")
  self.assertTrue(r["games"]["1"]["teams"]["OKC"]["roster_complete"])
  self.assertFalse(r["status_feed_produced"])
  self.assertEqual(len(r["games"]["1"]["teams"]["PHX"]["players"]),7)
 def test_duplicate_ids_fail(self):
  with self.assertRaises(ValueError):extract_roster({"athletes":[{"id":"1","displayName":"A"},{"id":"1","displayName":"B"}]})
if __name__=="__main__":unittest.main()
