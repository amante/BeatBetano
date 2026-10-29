import unittest
from nhl.pulso_crs_bridge_213 import integrate
class Tests(unittest.TestCase):
 def setUp(self):
  self.fixture={"game_id":"123","home":"EDM","away":"COL","start_utc":"2026-10-31T23:00:00Z"}
  self.coverage={"game_id":"123","available_for_numeric_crs":False,
    "projection_identity_coverage_complete":True,"captured_at":"2026-10-30T15:00:00Z",
    "teams":[{"team":"EDM","projected_skater_ids":["1"]},{"team":"COL","projected_skater_ids":["2"]}]}
 def test_absent_team_input_blocks(self):
  r=integrate(self.fixture,self.coverage,{})
  self.assertEqual(r["status"],"blocked")
  self.assertIsNone(r["probabilities"])
 def test_late_editorial_rejected(self):
  self.coverage["captured_at"]=self.fixture["start_utc"]
  with self.assertRaises(ValueError):integrate(self.fixture,self.coverage,{})
 def test_unverified_availability_blocks(self):
  inp={t:{"expected":{"players":[{"player_id":i,"status":"projected","unit":"top6"}]},
      "baseline":{},"history":{},"availability_independently_verified":False} for i,t in [(1,"EDM"),(2,"COL")]}
  self.assertIn("unverified_availability_EDM",integrate(self.fixture,self.coverage,inp)["issues"])
 def test_verified_but_missing_timestamp_blocks(self):
  inp={t:{"expected":{"players":[{"player_id":i,"status":"projected","unit":"top6"}]},
      "baseline":{},"history":{},"availability_independently_verified":True} for i,t in [(1,"EDM"),(2,"COL")]}
  self.assertIn("missing_source_timestamp_EDM",integrate(self.fixture,self.coverage,inp)["issues"])
if __name__=="__main__":unittest.main()
