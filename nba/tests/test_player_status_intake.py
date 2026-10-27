import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player_status_intake import reconcile
S={"content_sha256":"h","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX","tipoff_utc":"2026-10-27T01:00:00Z"}]}
R={"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"players":[{"player_id":"1","player":"Álex Caruso"}]},"PHX":{"players":[]}}}}}
def source(time="2026-10-27T00:00:00Z"):
 return {"games":{"1":{"supplementary_injury_observations":{"source":"https://site.api.espn.com/injuries","observed_at_utc":time,"items":[{"team":"OKC","player":"Alex Caruso","status":"Out"}]}}}}
class Tests(unittest.TestCase):
 def test_matching_and_out(self):
  a=reconcile(S,R,source())
  self.assertEqual(a["games"]["1"]["teams"]["OKC"][0]["player_id"],"1")
  self.assertEqual(a["games"]["1"]["teams"]["OKC"][0]["status"],"out")
  self.assertTrue(a["does_not_confirm_active_players"])
 def test_future_evidence_not_used(self):
  a=reconcile(S,R,source("2026-10-27T02:00:00Z"))
  self.assertEqual(a["games"]["1"]["teams"]["OKC"],[])
 def test_unmatched_name_not_assigned(self):
  a=source();a["games"]["1"]["supplementary_injury_observations"]["items"][0]["player"]="Unknown"
  self.assertEqual(len(reconcile(S,R,a)["unmatched_claims"]),1)
 def test_no_injury_not_healthy(self):
  a=source();a["games"]["1"]["supplementary_injury_observations"]["items"]=[]
  self.assertEqual(reconcile(S,R,a)["games"]["1"]["teams"]["OKC"],[])
if __name__=="__main__":unittest.main()
