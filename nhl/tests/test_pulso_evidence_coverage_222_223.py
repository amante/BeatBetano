import unittest
from nhl.pulso_evidence_coverage_222_223 import analyze
class CoverageTests(unittest.TestCase):
 def setUp(self):
  self.report={"data_kind":"source_readiness_only","generated_at_utc":"2026-10-29T21:00:00Z",
   "games":[{"game_id":"99","home":"EDM","away":"COL","start_utc":"2026-10-30T00:00:00Z"}]}
 def test_pool_and_editorial_are_not_confirmed_lineup(self):
  result=analyze(self.report,{"rosters":{"EDM":{"players":[{"id":1}]}}},{"goalies":[]},{"fixture_attested":False})
  self.assertTrue(result["games"][0]["teams"]["EDM"]["coverage"]["roster_pool"])
  self.assertFalse(result["games"][0]["teams"]["EDM"]["coverage"]["lineup_18_confirmed"])
  self.assertFalse(result["games"][0]["teams"]["EDM"]["coverage"]["goalie_confirmed"])
  self.assertEqual(result["full_model_ready"],0)
 def test_late_capture_rejected(self):
  self.report["generated_at_utc"]="2026-10-30T00:00:00Z"
  with self.assertRaises(ValueError):analyze(self.report,{},{"goalies":[]},{})
 def test_unsourced_crs_stays_missing(self):
  r=analyze(self.report,{},{"goalies":[]},{},crs={"99":{"as_of":"2026-10-29T20:00:00Z","skater_crs_proxies":{"EDM":{"score":1}}}})
  self.assertFalse(r["games"][0]["teams"]["EDM"]["coverage"]["skater_crs"])
 def test_verified_context_without_defense(self):
  r=analyze(self.report,{},{"goalies":[]},{},collective={"99":{"as_of":"2026-10-29T20:00:00Z","source_attestation_verified":True,
   "teams":{"EDM":{"pp":0.2,"pk":0.8,"rest":1}},"rivalry":False}})
  flags=r["games"][0]["teams"]["EDM"]["coverage"]
  self.assertTrue(flags["pp"]);self.assertTrue(flags["pk"]);self.assertTrue(flags["rest"])
  self.assertFalse(flags["defense_unit"])
if __name__=="__main__":unittest.main()
