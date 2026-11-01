import unittest,tempfile,json
from pathlib import Path
from nhl.pulso_daily_slate_274 import build
from nhl.historical_target_walkforward import CATEGORIES
from nhl.pulso_collective_audit_208 import freeze_prediction
class DailySlate274(unittest.TestCase):
 def source(self):
  fixtures=[{"game_id":str(i),"home":"AAA","away":"BBB","scheduled_start":"2026-11-01T23:00:00Z","game_state":"FUT"} for i in range(12)]
  schedule={"fixtures":fixtures,"source_url":"https://api-web.nhle.com/v1/score/2026-11-01","captured_at":"2026-11-01T14:00:00Z"}
  report={"data_kind":"source_readiness_only","date":"2026-11-01","official_predictions":0,"games":[{"game_id":str(i),"home":"AAA","away":"BBB","start_utc":"2026-11-01T23:00:00Z"} for i in range(10)]}
  return schedule,report
 def write(self,folder,gid):
  for market,cats in CATEGORIES.items():
   r={"game_id":str(gid),"home":"AAA","away":"BBB","start_utc":"2026-11-01T23:00:00Z",
   "market":market,"model_version":"outcome-only-206-frozen-params","source_url":"https://example.org",
   "prediction_as_of_utc":"2026-11-01T14:00:00Z","source_asof_utc":"2026-11-01T14:00:00Z",
   "point_in_time_sources_verified":True,"probabilities":{c:1/len(cats) for c in cats},
   "official":False,"odds_used_in_model":False}
   (folder/f"{gid}-{market}.json").write_text(json.dumps(freeze_prediction(r)))
 def test_preserves_entire_schedule(self):
  s,r=self.source()
  with tempfile.TemporaryDirectory() as d:
   for gid in range(8):self.write(Path(d),gid)
   out=build(s,r,d)
   self.assertEqual(out["official_schedule_games"],12)
   self.assertEqual(out["experimental_predicted_games"],8)
   self.assertEqual(out["pregame_forecast_unavailable"],2)
   self.assertEqual(out["not_pregame_at_capture"],2)
 def test_partial_market_rejected(self):
  s,r=self.source()
  with tempfile.TemporaryDirectory() as d:
   self.write(Path(d),0)
   (Path(d)/"0-ml.json").unlink()
   with self.assertRaises(ValueError):build(s,r,d)
 def test_duplicate_official_id_rejected(self):
  s,r=self.source();s["fixtures"].append(s["fixtures"][0])
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):build(s,r,d)
if __name__=="__main__":unittest.main()
