import unittest
from nhl.pulso_training_ledger_215 import assemble,FEATURES
class TrainingLedger215(unittest.TestCase):
 def setUp(self):
  self.label={"game_id":"1","date":"2026-10-01","home":"EDM","away":"COL","ml_winner":"home","rt_result":"home","first_to_plus3":"home","home_reached_plus3":"True","away_reached_plus3":"False"}
  self.row={"game_id":"1","date":"2026-10-01","home":"EDM","away":"COL","as_of":"2026-10-01T17:00:00Z","start_utc":"2026-10-01T23:00:00Z",
   "official":False,"odds_used":False,"source_attestation_verified":True,"frozen_before_start":True,"source_sha256":"a"*64,
   "issues":[],"status":"research_vector_complete",
   "teams":{t:{k:1.0 for k in FEATURES} for t in ("EDM","COL")}}
 def test_valid_but_not_enough_training_coverage(self):
  r=assemble([self.row],[self.label])
  self.assertEqual(r["accepted"],1)
  self.assertFalse(r["eligible_for_collective_training"])
  self.assertEqual(r["rows"][0]["target"]["ml"],"home")
 def test_after_puck_drop_is_rejected(self):
  self.row["as_of"]=self.row["start_utc"]
  self.assertEqual(assemble([self.row],[self.label])["reject_reasons"]["invalid_or_late_freeze"],1)
 def test_unattested_sources_are_rejected(self):
  self.row["source_attestation_verified"]=False
  self.assertEqual(assemble([self.row],[self.label])["accepted"],0)
 def test_incomplete_vector_not_imputed(self):
  del self.row["teams"]["COL"]["pp_bayes"]
  self.assertEqual(assemble([self.row],[self.label])["reject_reasons"]["missing_numeric_feature"],1)
 def test_duplicate_snapshot_rejected(self):
  with self.assertRaises(ValueError):assemble([self.row,self.row],[self.label])
 def test_postgame_fixture_mismatch_rejected(self):
  self.label["away"]="VAN"
  self.assertEqual(assemble([self.row],[self.label])["reject_reasons"]["fixture_label_mismatch"],1)
if __name__=="__main__":unittest.main()
