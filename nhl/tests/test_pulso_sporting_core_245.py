import unittest
from nhl.pulso_sporting_core_245 import integrate,contribution,MODULES
class OriginalCore245(unittest.TestCase):
 def setUp(self):
  stamp="2026-10-30T12:00:00Z";start="2026-10-30T23:00:00Z"
  self.report={"data_kind":"source_readiness_only","official_predictions":0,"generated_at_utc":stamp,
   "games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":start}]}
  self.bridge={"kind":"sporting_source_bridge","as_of":stamp,"games":{"1":{
   "game_id":"1","home":"BOS","away":"MTL","start_utc":start,"as_of":stamp,
   "teams":{t:{"roster_identity_available":True,"provider_goalie_id_observed":None,
    "goalie_confirmed_independently":False} for t in ("BOS","MTL")}}}}
 def test_never_silently_use_statistical_substitute(self):
  x=integrate(self.report,self.bridge,{})
  g=x["games"][0]
  self.assertIsNone(g["sporting_probabilities"])
  self.assertEqual(set(g["module_manifest"]),set(MODULES))
  self.assertTrue(all(not m["applied_to_sporting_probability"] for m in g["module_manifest"].values()))
  self.assertFalse(x["forecast_promotion_allowed"])
 def test_verified_evidence_is_not_fitted(self):
  stamp=self.report["generated_at_utc"]
  self.bridge["games"]["1"]["teams"]["BOS"]["provider_goalie_id_observed"]=42
  packages={"1":{t:{"crs":{"source_url":"https://nhl.com","as_of":stamp,
    "availability_independently_verified":True,"lineup_identity_verified":True,"offense_proxy":1.2,"availability_delta":0.1}}
    for t in ("BOS","MTL")}}
  x=integrate(self.report,self.bridge,packages)
  m=x["games"][0]["module_manifest"]["crs"]
  self.assertTrue(m["observed"])
  self.assertFalse(m["applied_to_sporting_probability"])
 def test_future_capture_is_rejected(self):
  self.report["generated_at_utc"]="2026-10-31T12:00:00Z"
  with self.assertRaises(ValueError):integrate(self.report,self.bridge,{})
 def test_unsupported_claim_rejected(self):
  with self.assertRaises(ValueError):contribution("goalie",None,None,True,applied=True,effect=.1)
 def test_fixture_mismatch(self):
  self.bridge["games"]["1"]["away"]="TOR"
  with self.assertRaises(ValueError):integrate(self.report,self.bridge,{})
if __name__=="__main__":unittest.main()
