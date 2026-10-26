import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_gap_diagnostics import diagnose
S={"predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK"}]}
class Tests(unittest.TestCase):
 def test_fails_closed_and_reports_missing_sources(self):
  r=diagnose(S,{"official_document_retrieved":False,"retrieval_error_type":"HTTPError"},
    {"games":{"1":{"is_pregame_evidence":False}}},{},{"games":{"1":{}}},{"games":1,"complete_pregame_features":0})
  self.assertEqual(r["missing_evidence_reasons"]["nba_pdf_unavailable"],1)
  self.assertFalse(r["calibrated_availability_impact"])
 def test_espn_does_not_confirm_lineups(self):
  r=diagnose(S,{"official_document_retrieved":True},
    {"games":{"1":{"is_pregame_evidence":True,"injury_observations":[{"player":"Example"}]}}},
    {"games":{"1":{"supplementary_injury_observations":{"items":[{"player":"Example"}]}}}},
    {"games":{"1":{}}},{"games":1,"complete_pregame_features":0})
  self.assertEqual(r["per_game"][0]["espn_preview_injury_observations"],1)
  self.assertFalse(r["per_game"][0]["both_starting_fives_verified"])
 def test_wrong_slate_coverage_rejected(self):
  with self.assertRaises(ValueError):
   diagnose(S,{}, {},{},{},{"games":9})
if __name__=="__main__":unittest.main()
