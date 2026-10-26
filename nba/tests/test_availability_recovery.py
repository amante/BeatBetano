import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability_recovery import recover
S={"content_sha256":"sha","predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-26T23:00:00Z"}]}
P={"snapshot_sha256":"sha","games":{"1":{"is_pregame_evidence":True,"observed_at_utc":"2026-10-26T20:00:00Z","source_url":"https://espn.test","injury_observations":[{"player":"Test Player","status":"Out"}]}}}
class Tests(unittest.TestCase):
 def test_recovers_supplementary_not_official(self):
  row=recover(S,{},P)["games"]["1"]
  self.assertEqual(row["recovered_count"],1)
  self.assertIsNone(row["recovered_summary_claims"][0]["team"])
  self.assertFalse(row["probability_adjustment_authorized"])
 def test_no_posttip_leak(self):
  p={"snapshot_sha256":"sha","games":{"1":dict(P["games"]["1"],observed_at_utc="2026-10-27T00:00:00Z")}}
  self.assertEqual(recover(S,{},p)["games"]["1"]["recovered_count"],0)
 def test_does_not_duplicate_existing_injury_feed(self):
  sporting={"games":{"1":{"supplementary_injury_observations":{"observed_at_utc":"2026-10-26T19:00:00Z","items":[{"player":"X"}]}}}}
  self.assertEqual(recover(S,sporting,P)["games"]["1"]["recovered_count"],0)
 def test_snapshot_mismatch(self):
  with self.assertRaises(ValueError):recover(S,{},dict(P,snapshot_sha256="wrong"))
if __name__=="__main__":unittest.main()
