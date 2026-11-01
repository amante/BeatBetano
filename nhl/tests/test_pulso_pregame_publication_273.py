import unittest,tempfile,json
from pathlib import Path
from nhl.pulso_pregame_publication_273 import audit
from nhl.historical_target_walkforward import CATEGORIES
class Publication273(unittest.TestCase):
 def fixture(self):
  return {"game_id":"77","home":"A","away":"B","start_utc":"2026-11-01T21:00:00+00:00"}
 def payload(self):
  return {"data_kind":"source_readiness_only","official_predictions":0,"games":[self.fixture()]}
 def write(self,root,market,modify=None):
  probabilities={v:1/len(CATEGORIES[market]) for v in CATEGORIES[market]}
  r={**self.fixture(),"market":market,"probabilities":probabilities,"official":False,
   "odds_used_in_model":False,"model_version":"outcome-only-206-frozen-params",
   "point_in_time_sources_verified":True,"historical_labels_sha256":"a"*64,
   "prediction_as_of_utc":"2026-11-01T14:00:00+00:00","source_asof_utc":"2026-11-01T14:00:00+00:00"}
  if modify:modify(r)
  (root/(market+".json")).write_text(json.dumps({"record":r}))
 def test_complete_markets(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for m in CATEGORIES:self.write(root,m)
   r=audit(self.payload(),d)
   self.assertEqual(r["frozen_forecasts"],5)
   self.assertFalse(r["full_model_validated"])
 def test_incomplete_markets_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   self.write(Path(d),"ml")
   with self.assertRaises(ValueError):audit(self.payload(),d)
 def test_future_leakage_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   for m in CATEGORIES:self.write(Path(d),m,lambda r:r.update(prediction_as_of_utc="2026-11-01T22:00:00+00:00"))
   with self.assertRaises(ValueError):audit(self.payload(),d)
 def test_wrong_probabilities_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   for m in CATEGORIES:self.write(Path(d),m)
   self.write(Path(d),"ml",lambda r:r["probabilities"].update(home=.9))
   with self.assertRaises(ValueError):audit(self.payload(),d)
 def test_empty_if_started(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(audit(self.payload(),d)["predicted_fixture_count"],0)
if __name__=="__main__":unittest.main()
