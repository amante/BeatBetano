import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injury_lineup_joint import compile_report
SNAP={"created_at_utc":"2026-10-26T15:00:00Z","predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-26T23:00:00Z"}]}
def official(download):
 return {"official_document_retrieved":True,"source_report_as_of_utc":"2026-10-26T16:00:00Z",
 "downloaded_at_utc":download,"raw_page_text":["Boston Celtics Brown, Jaylen Questionable"],
 "report_url":"https://ak-static.cms.nba.com/report.pdf"}
class Tests(unittest.TestCase):
 def test_later_than_snapshot_but_before_tip_is_separate_evidence(self):
  r=compile_report(SNAP,official("2026-10-26T17:00:00Z"))
  row=r["games"]["1"]
  self.assertTrue(row["source_time_validated"])
  self.assertTrue(row["separate_post_snapshot_evidence"])
  self.assertEqual(len(row["official_structured_candidate_rows"]),1)
  self.assertFalse(row["official_player_team_status_confirmed"])
 def test_after_tip_is_rejected(self):
  r=compile_report(SNAP,official("2026-10-27T00:00:00Z"))
  self.assertEqual(r["official_player_rows_resolved"],0)
 def test_no_tip_fails_closed(self):
  bad={"created_at_utc":SNAP["created_at_utc"],"predictions":[dict(SNAP["predictions"][0])]}
  del bad["predictions"][0]["tipoff_utc"]
  self.assertFalse(compile_report(bad,official("2026-10-26T17:00:00Z"))["games"]["1"]["source_time_validated"])
if __name__=="__main__":unittest.main()
