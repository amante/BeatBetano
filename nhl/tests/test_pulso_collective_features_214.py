import unittest
from nhl.pulso_collective_features_214 import build
class Test214(unittest.TestCase):
 def setUp(self):
  self.f={"game_id":"1","home":"EDM","away":"COL","start_utc":"2026-11-01T23:00:00Z"}
  self.crs={"game_id":"1","issues":[],"skater_crs_proxies":{}}
  self.g={"goalies":[]}
  self.ctx={"home":"EDM","away":"COL","rest_days":{},"special_teams":{}}
 def test_incomplete_blocks_probabilities(self):
  r=build(self.f,self.crs,self.g,self.ctx,"2026-11-01T14:00:00Z")
  self.assertIn("missing_crs_EDM",r["issues"])
  self.assertIsNone(r["ml_probabilities"])
  self.assertFalse(r["official"])
 def test_post_start_rejected(self):
  with self.assertRaises(ValueError):build(self.f,self.crs,self.g,self.ctx,self.f["start_utc"])
 def test_wrong_fixture_rejected(self):
  self.crs["game_id"]="5"
  with self.assertRaises(ValueError):build(self.f,self.crs,self.g,self.ctx,"2026-11-01T14:00:00Z")
 def test_context_mismatch_rejected(self):
  self.ctx["away"]="VAN"
  with self.assertRaises(ValueError):build(self.f,self.crs,self.g,self.ctx,"2026-11-01T14:00:00Z")
if __name__=="__main__":unittest.main()
