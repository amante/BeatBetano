import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evidence_reconciliation import reconcile
S={"content_sha256":"hash","predictions":[{"game_id":"10","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-27T00:00:00Z"}]}
def evidence(items):
 return {"snapshot_sha256":"hash","games":{"10":{"espn_injury_observations":items,
 "bleacher_report_headline_alerts":[{"published_at_utc":"2026-10-26T15:00:00Z","collected_at_utc":"2026-10-26T16:00:00Z"}]}}}
class Tests(unittest.TestCase):
 def test_deduplicate_without_false_independent_confirmation(self):
  r=reconcile(S,evidence([{"team":"BOS","player":"Jaylen Brown","status":"Out"}]*2))["games"]["10"]
  self.assertEqual(r["unique_structured_players"],1)
  self.assertEqual(r["duplicate_espn_records"],1)
  self.assertEqual(r["players"][0]["independent_source_count"],0)
 def test_conflicts_fail_closed(self):
  r=reconcile(S,evidence([{"team":"BOS","player":"J. Brown","status":"Out"},
    {"team":"BOS","player":"J. Brown","status":"Available"}]))["games"]["10"]
  self.assertEqual(r["conflicting_espn_statuses"],1)
  self.assertIsNone(r["players"][0]["availability_for_model"])
 def test_no_unrelated_team(self):
  r=reconcile(S,evidence([{"team":"LAL","player":"A","status":"Out"}]))["games"]["10"]
  self.assertEqual(r["unique_structured_players"],0)
 def test_hash_check(self):
  with self.assertRaises(ValueError):reconcile(S,{"snapshot_sha256":"wrong"})
if __name__=="__main__":unittest.main()
