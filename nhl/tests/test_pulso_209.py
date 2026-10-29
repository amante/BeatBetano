import tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from nhl.pulso_block_audit_209 import evaluate
from nhl.pulso_prospective_ledger_209 import archive
class Tests(unittest.TestCase):
 def test_bootstrap_identical_predictions(self):
  from unittest.mock import patch
  entries=[{"date":(datetime(2026,3,1,tzinfo=timezone.utc)+timedelta(days=i)).date().isoformat(),"y":{"ml":"home"},"probs":{"ml":[.7,.3]},"baseline_probs":{"ml":[.7,.3]}} for i in range(28)]
  with patch("nhl.pulso_block_audit_209.CATEGORIES",{"ml":("home","away")}):
   r=evaluate(entries,replicates=100)
  self.assertEqual(r["markets"]["ml"]["confidence"]["brier"]["block_ci95"],[0.,0.])
 def test_append_only_and_post_start_gate(self):
  t=datetime.now(timezone.utc);future=(t+timedelta(hours=2)).isoformat()
  report={"generated_at_utc":t.isoformat(),"data_kind":"source_readiness_only","official_predictions":0,
    "games":[{"game_id":"5","start_utc":future,"official":False,"probabilities":None}]}
  with tempfile.TemporaryDirectory() as folder:
   archive(report,folder,"42")
   with self.assertRaises(FileExistsError):archive(report,folder,"42")
   report["games"][0]["start_utc"]=t.isoformat()
   with self.assertRaises(ValueError):archive(report,folder,"43")
if __name__=="__main__":unittest.main()
