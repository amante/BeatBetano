import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lineup_roster_reconciliation import reconcile
S={"content_sha256":"x","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX"}]}
R={"snapshot_sha256":"x","games":{"1":{"teams":{"OKC":{"provisional_rotation":[{"player_id":"123","player":"Alex Caruso","minutes_projection":18}]}}}}}
L={"snapshot_sha256":"x","games":{"1":{"teams":{"OKC":{"starters":["Alex Caruso","Other"],"lineup_status":"projected","source_provider":"rotowire"}}}}}
class Tests(unittest.TestCase):
 def test_name_matching_never_approves_allocation(self):
  g=reconcile(S,R,L)["games"]["1"]["teams"]["OKC"]
  self.assertEqual(g["matched_starters"][0]["player_id"],"123")
  self.assertEqual(g["unmatched_starters"],["Other"])
  self.assertFalse(g["allocation_ready"])
 def test_hash_fail(self):
  q=dict(L,snapshot_sha256="wrong")
  with self.assertRaises(ValueError):reconcile(S,R,q)
if __name__=="__main__":unittest.main()
