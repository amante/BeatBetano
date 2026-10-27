import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from joint_minutes_report import build
S={"content_sha256":"hash","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX","tipoff_utc":"2026-10-27T00:00:00Z"}]}
R={"snapshot_sha256":"hash","games":{"1":{"teams":{"OKC":{"provisional_rotation":[{"player_id":str(i),"minutes_projection":25} for i in range(7)]}}}}}
def avail(verified=True):
 return {"snapshot_sha256":"hash","games":{"1":{"teams":{"OKC":{"observed_at_utc":"2026-10-26T23:00:00Z","roster_complete":True,"availability_source_verified":verified,"players":[{"player_id":str(i),"status":"out" if i==6 else "available","max_minutes":48} for i in range(7)]}}}}}
class Tests(unittest.TestCase):
 def test_verified_joint_budget_and_out_zero(self):
  x=build(S,R,avail())["games"]["1"]["teams"]["OKC"]
  self.assertEqual(x["status"],"provisional_joint_allocation")
  self.assertAlmostEqual(sum(x["allocations"].values()),240)
  self.assertEqual(x["allocations"]["6"],0)
 def test_unverified_no_minutes(self):
  self.assertIsNone(build(S,R,avail(False))["games"]["1"]["teams"]["OKC"]["allocations"])
 def test_no_future_data(self):
  a=avail();a["games"]["1"]["teams"]["OKC"]["observed_at_utc"]="2026-10-27T00:01:00Z"
  self.assertIsNone(build(S,R,a)["games"]["1"]["teams"]["OKC"]["allocations"])
 def test_unmatched_roster_fails_closed(self):
  a=avail();a["games"]["1"]["teams"]["OKC"]["players"].append({"player_id":"unknown","status":"available"})
  self.assertEqual(build(S,R,a)["games"]["1"]["teams"]["OKC"]["status"],"missing_historical_player_weights")
if __name__=="__main__":unittest.main()
