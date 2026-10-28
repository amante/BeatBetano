import unittest
from multisport.model_registry import registry_report
from multisport.data_lineage import verify_manifest

class ModelRegistryTests(unittest.TestCase):
 def record(self):
  return {"sport":"nhl","model_name":"goals_ml","version":"2026-27.2",
    "feature_cutoff_utc":"2026-10-27T19:00:00Z",
    "training_cutoff_utc":"2026-10-26T00:00:00Z",
    "dataset_sha256":"a"*64,"code_revision":"123abc",
    "calibration_report":None,"validation_state":"research"}
 def test_unvalidated_never_published(self):
  result=registry_report([self.record()])
  self.assertFalse(result["entries"][0]["release_eligible"])
  self.assertFalse(result["automatic_promotion"])
 def test_validation_requires_real_evidence(self):
  x=self.record();x["validation_state"]="independently_validated"
  with self.assertRaises(ValueError):registry_report([x])
 def test_duplicate_version_rejected(self):
  with self.assertRaises(ValueError):registry_report([self.record(),self.record()])
 def test_source_from_future_rejected(self):
  manifest={"prediction_as_of_utc":"2026-10-27T19:00:00Z","event_start_utc":"2026-10-27T22:00:00Z",
    "odds_used_in_model":False,"sources":[{"source_id":"nhl","observed_at_utc":"2026-10-27T20:00:00Z","content_sha256":"b"*64}]}
  with self.assertRaises(ValueError):verify_manifest(manifest)
 def test_valid_manifest_still_not_claim_authenticity(self):
  manifest={"prediction_as_of_utc":"2026-10-27T19:00:00Z","event_start_utc":"2026-10-27T22:00:00Z",
    "odds_used_in_model":False,"sources":[{"source_id":"nhl","observed_at_utc":"2026-10-27T18:00:00Z","content_sha256":"b"*64}]}
  x=verify_manifest(manifest)
  self.assertTrue(x["point_in_time_checks_passed"])
  self.assertFalse(x["independent_source_authenticity_verified"])
if __name__=="__main__":unittest.main()
