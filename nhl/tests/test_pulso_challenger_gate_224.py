import unittest
from nhl.pulso_challenger_gate_224 import audit,REQUIRED
class Tests(unittest.TestCase):
 def row(self,i,day):
  return {"game_id":str(i),"date":day,"frozen_as_of":day+"T12:00:00Z","source_sha256":"a"*64,
   "home":"EDM","away":"COL","features":{team:{x:1. for x in REQUIRED} for team in ("EDM","COL")}}
 def test_no_data_fails_closed(self):
  self.assertEqual(audit({"status":"training_dataset_research_only","rows":[]})["reason"],"no_verified_historical_asof_rows")
 def test_small_dataset_blocks(self):
  rows=[self.row(i,"2026-10-"+str(10+i).zfill(2)) for i in range(5)]
  result=audit({"status":"training_dataset_research_only","rows":rows})
  self.assertFalse(result["training_permitted"])
  self.assertEqual(result["train"],4)
 def test_larger_temporal_cohort_is_gate_ready(self):
  from datetime import date,timedelta
  rows=[self.row(i,(date(2025,10,1)+timedelta(days=i//3)).isoformat()) for i in range(450)]
  result=audit({"status":"training_dataset_research_only","rows":rows})
  self.assertTrue(result["training_permitted"])
  self.assertTrue(result["train"]>=200)
  self.assertTrue(result["test"]>=100)
 def test_missing_variable_rejected(self):
  x=self.row(1,"2026-10-01");del x["features"]["COL"]["pp_bayes"]
  with self.assertRaises(ValueError):audit({"status":"training_dataset_research_only","rows":[x]})
 def test_duplicate_rejected(self):
  x=self.row(1,"2026-10-01")
  with self.assertRaises(ValueError):audit({"status":"training_dataset_research_only","rows":[x,x]})
if __name__=="__main__":unittest.main()
