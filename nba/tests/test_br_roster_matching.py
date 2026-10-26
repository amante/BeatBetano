import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from br_roster_matching import roster_names,contains,match
S={"content_sha256":"hash","predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-27T00:00:00Z"}]}
def alert(name="Jayson Tatum",collected="2026-10-26T19:00:00Z"):
 return {"headline":"NBA: "+name+" out tonight with injury","url":"https://bleacherreport.com/articles/test",
 "published_at_utc":"2026-10-26T18:00:00Z","collected_at_utc":collected}
def evidence(a):
 return {"snapshot_sha256":"hash","games":{"1":{"bleacher_report_headline_alerts":a}}}
class Resp:
 def __init__(self,data):self.data=data
 def raise_for_status(self):pass
 def json(self):return self.data
class Sess:
 def get(self,url,timeout=0):
  return Resp({"athletes":[{"id":"7","displayName":"Jayson Tatum"}]} if "/bos/" in url else
   {"athletes":[{"id":"8","displayName":"Jalen Brunson"}]})
class Tests(unittest.TestCase):
 def test_full_name_boundary(self):
  self.assertTrue(contains("Jayson Tatum injured","Jayson Tatum"))
  self.assertFalse(contains("Jay Tatum injured","Jayson Tatum"))
 def test_roster_group_shape(self):
  self.assertEqual(roster_names({"athletes":[{"items":[{"id":"2","displayName":"A B"}]}]}),[{"name":"A B","id":"2"}])
 def test_unique_identity_not_health(self):
  g=match(S,evidence([alert()]),Sess())["games"]["1"]
  self.assertEqual(g["matched_count"],1)
  self.assertIsNone(g["matched_editorial_mentions"][0]["availability_status"])
 def test_late_source_excluded(self):
  g=match(S,evidence([alert(collected="2026-10-27T01:00:00Z")]),Sess())["games"]["1"]
  self.assertEqual(g["matched_count"],0)
 def test_ambiguous_suppressed(self):
  class Same:
   def get(self,url,timeout=0):return Resp({"athletes":[{"displayName":"Jayson Tatum","id":"7"}]})
  g=match(S,evidence([alert()]),Same())["games"]["1"]
  self.assertEqual(g["matched_count"],0);self.assertEqual(g["ambiguous_headlines"],1)
if __name__=="__main__":unittest.main()
