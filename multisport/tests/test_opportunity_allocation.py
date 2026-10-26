import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from opportunity_allocation import allocate
def player(i,status="available",w=1,cap=48):
 return {"player_id":str(i),"status":status,"expected_weight":w,"max_units":cap}
class Tests(unittest.TestCase):
 def test_nba_240_and_out_zero(self):
  r=allocate("nba","minutes",[player(i) for i in range(6)]+[player(7,"out")])
  self.assertEqual(r["status"],"provisional_joint_allocation")
  self.assertAlmostEqual(sum(r["allocations"].values()),240)
  self.assertEqual(r["allocations"]["7"],0)
 def test_reallocated_when_player_out(self):
  base=allocate("nba","minutes",[player(i,cap=48) for i in range(6)])
  cut=allocate("nba","minutes",[player(i,cap=48) for i in range(6)]+[player("X","out")])
  self.assertEqual(base["allocations"],{k:v for k,v in cut["allocations"].items() if k!="X"})
 def test_nfl_targets_budget(self):
  r=allocate("nfl","targets",[player("WR1",w=3,cap=15),player("WR2",w=1,cap=15)],total=16)
  self.assertAlmostEqual(sum(r["allocations"].values()),16)
  self.assertGreater(r["allocations"]["WR1"],r["allocations"]["WR2"])
 def test_nhl_ice_time(self):
  r=allocate("nhl","skater_minutes",[player(i,cap=50) for i in range(8)])
  self.assertEqual(sum(r["allocations"].values()),300)
 def test_soccer_regulation(self):
  r=allocate("soccer","minutes",[player(i,cap=90) for i in range(12)])
  self.assertAlmostEqual(sum(r["allocations"].values()),990)
 def test_questionable_not_assumed_available(self):
  r=allocate("nba","minutes",[player(i) for i in range(6)]+[player("X","questionable")])
  self.assertEqual(r["status"],"requires_availability_scenarios")
 def test_infeasible(self):
  r=allocate("nba","minutes",[player(i) for i in range(3)])
  self.assertEqual(r["status"],"infeasible")
 def test_tennis_excluded(self):
  with self.assertRaises(ValueError):allocate("tennis","minutes",[],total=1)
if __name__=="__main__":unittest.main()
