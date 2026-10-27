import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verified_absence_history import build
E=[{"game_id":"1","home_team":"OKC","away_team":"PHX","tipoff_utc":"2026-10-25T01:00:00Z"}]
ids=[str(x) for x in range(6)]
B=[{"game_id":"1","pregame_roster_ids_by_team":{"OKC":ids},"player_minutes_by_team":{"OKC":{i:40 for i in ids}}}]
def claims():
 return [{"game_id":"1","team":"OKC","player_id":i,"status":"out" if i=="5" else "available","observed_at_utc":"2026-10-25T00:00:00Z","source_url":"https://nba.example/status","official_verified":True} for i in ids]
class Tests(unittest.TestCase):
 def test_complete_certified(self):
  r=build(E,claims(),B);self.assertEqual(len(r["games"]),1);self.assertEqual(r["games"][0]["confirmed_out_player_ids"],["5"])
 def test_partial_is_not_verification(self):
  r=build(E,claims()[:2],B);self.assertEqual(len(r["games"]),0)
 def test_future_claim_is_rejected(self):
  c=claims();c[0]["observed_at_utc"]="2026-10-25T02:00:00Z"
  self.assertFalse(build(E,c,B)["games"])
 def test_unverified_source_is_rejected(self):
  c=claims();c[0]["official_verified"]=False
  self.assertFalse(build(E,c,B)["games"])
if __name__=="__main__":unittest.main()
