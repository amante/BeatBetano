import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_readiness_audit import audit
S={"content_sha256":"h","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX"}]}
R={"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"roster_complete":True,"players":[{"player_id":"1"}]}}}}}
A={"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"roster_complete":True,"allocation_ready":False,"unresolved_player_ids":["1"]}}}}}
M={"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"status":"unresolved_statuses","allocations":None}}}}}
class Tests(unittest.TestCase):
 def test_unverified_never_ready(self):
  q=audit(S,R,A,M)
  self.assertEqual(q["complete_rotation_games"],0)
  self.assertFalse(q["games"]["1"]["teams"]["OKC"]["rotation_ready"])
 def test_verified_240(self):
  A["games"]["1"]["teams"]["OKC"]["allocation_ready"]=True
  M["games"]["1"]["teams"]["OKC"]["allocations"]={"1":240}
  q=audit(S,R,A,M)
  self.assertTrue(q["games"]["1"]["teams"]["OKC"]["rotation_ready"])
  self.assertFalse(q["games"]["1"]["both_teams_rotation_ready"])
 def test_different_digest_fails(self):
  with self.assertRaises(ValueError):audit(S,{**R,"snapshot_sha256":"other"},A,M)
if __name__=="__main__":unittest.main()
