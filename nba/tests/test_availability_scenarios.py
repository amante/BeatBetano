import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability_scenarios import scenarios
S={"content_sha256":"h","predictions":[{"game_id":"1","home_team":"OKC","away_team":"PHX","tipoff_utc":"2026-10-28T01:00:00Z"}]}
R={"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"provisional_rotation":[{"player_id":str(i),"minutes_projection":25} for i in range(8)]}}}}}
def data():
 players=[{"player_id":str(i),"status":"questionable" if i==7 else "available","max_minutes":48} for i in range(8)]
 return {"snapshot_sha256":"h","games":{"1":{"teams":{"OKC":{"roster_complete":True,"observed_at_utc":"2026-10-28T00:00:00Z","players":players}}}}}
class Tests(unittest.TestCase):
 def test_branch_and_240(self):
  x=scenarios(S,R,data())["games"]["1"]["teams"]["OKC"]
  self.assertEqual(len(x["branches"]),2)
  for b in x["branches"]:
   self.assertEqual(b["status"],"provisional_joint_allocation")
   self.assertAlmostEqual(sum(b["allocations"].values()),240)
   if b["questionable_assumptions"]["7"]=="out":self.assertEqual(b["allocations"]["7"],0)
 def test_unknown_does_not_assume_active(self):
  v=data();v["games"]["1"]["teams"]["OKC"]["players"][2]["status"]="unknown"
  self.assertEqual(scenarios(S,R,v)["games"]["1"]["teams"]["OKC"]["status"],"unknown_availability_blocks")
 def test_unverified_roster(self):
  v=data();v["games"]["1"]["teams"]["OKC"]["roster_complete"]=False
  self.assertEqual(scenarios(S,R,v)["games"]["1"]["teams"]["OKC"]["branches"],[])
if __name__=="__main__":unittest.main()
