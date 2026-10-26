import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_coverage_scorecard import score,markdown
S={"content_sha256":"abc","predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK"}]}
M={"snapshot_sha256":"abc","br_retrieval_status":"retrieved","br_nba_injury_headlines":[{},{}],"games":{"1":{"bleacher_report_headline_alerts":[{},{}]}}}
R={"snapshot_sha256":"abc","games":{"1":{"unique_structured_players":2,"duplicate_espn_records":1,"conflicting_espn_statuses":1}}}
B={"snapshot_sha256":"abc","roster_retrieval_errors":{"NYK":"HTTPError"},"games":{"1":{"matched_count":1,"ambiguous_headlines":1}}}
class Tests(unittest.TestCase):
 def test_coverage_and_no_inflated_verification(self):
  r=score(S,M,R,B);s=r["summary"]
  self.assertEqual(s["br_unassigned_editorial_alerts"],1)
  self.assertEqual(s["espn_status_conflicts"],1)
  self.assertEqual(r["teams_with_roster_errors"],1)
  self.assertEqual(s["officially_verified_players"],0)
  self.assertFalse(r["calibrated_probabilities_authorized"])
 def test_hash_mismatch_fails(self):
  with self.assertRaises(ValueError):score(S,dict(M,snapshot_sha256="wrong"),R,B)
 def test_missing_rows_are_explicit_zero(self):
  empty={"snapshot_sha256":"abc","games":{}}
  r=score(S,empty,empty,empty)
  self.assertEqual(r["summary"]["games"],1)
  self.assertEqual(r["summary"]["br_athlete_mentions"],0)
 def test_markdown_distinguishes_editorial_from_official(self):
  self.assertIn("No official player availability",markdown(score(S,M,R,B)))
if __name__=="__main__":unittest.main()
