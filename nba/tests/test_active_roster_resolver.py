import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from active_roster_resolver import resolve
S={"content_sha256":"hash","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX","tipoff_utc":"2026-10-27T01:00:00Z"}]}
T="2026-10-27T00:00:00Z"
def feeds():
 r={"snapshot_sha256":"hash","games":{"1":{"teams":{"OKC":{"roster_complete":True,"observed_at_utc":T,"source_url":"https://team.example/roster","players":[{"player_id":str(i),"player":"Player "+str(i)} for i in range(6)]}}}}}
 st={"snapshot_sha256":"hash","games":{"1":{"teams":{"OKC":[{"player_id":str(i),"status":"out" if i==5 else "active","observed_at_utc":T,"source_url":"https://injury.example/status"} for i in range(6)]}}}}
 l={"snapshot_sha256":"hash","games":{}}
 return r,st,l
class Tests(unittest.TestCase):
 def test_available_and_out(self):
  r,st,l=feeds();data=resolve(S,r,st,l)["games"]["1"]["teams"]["OKC"]
  self.assertTrue(data["allocation_ready"])
  self.assertEqual(data["players"][5]["status"],"out")
 def test_missing_status_unknown(self):
  r,st,l=feeds();st["games"]["1"]["teams"]["OKC"].pop()
  data=resolve(S,r,st,l)["games"]["1"]["teams"]["OKC"]
  self.assertFalse(data["allocation_ready"])
  self.assertEqual(len(data["unresolved_player_ids"]),1)
 def test_future_roster_rejected(self):
  r,st,l=feeds();r["games"]["1"]["teams"]["OKC"]["observed_at_utc"]="2026-10-27T01:01:00Z"
  self.assertEqual(resolve(S,r,st,l)["games"]["1"]["teams"]["OKC"]["status"],"roster_unverified")
 def test_conflicting_claims_unresolved(self):
  r,st,l=feeds();st["games"]["1"]["teams"]["OKC"].append({"player_id":"1","status":"out","observed_at_utc":T,"source_url":"https://other.example"})
  self.assertFalse(resolve(S,r,st,l)["games"]["1"]["teams"]["OKC"]["allocation_ready"])
if __name__=="__main__":unittest.main()
