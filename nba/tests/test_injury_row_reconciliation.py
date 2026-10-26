import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injury_lineup_joint import structured_rows,compile_report
S={"created_at_utc":"2026-10-26T18:00:00Z","predictions":[{"game_id":"42","home_team":"BOS","away_team":"NYK"}]}
def source(download="2026-10-26T17:30:00Z"):
 return {"official_document_retrieved":True,"source_report_as_of_utc":"2026-10-26T17:00:00Z",
  "downloaded_at_utc":download,"raw_page_text":["BOS Smith, John Questionable - Knee\nNYK Jones, Mary Out - Ankle\nSmith, John Available\nBOS Doe, Jane Possible"],
  "report_url":"https://ak-static.cms.nba.com/report.pdf"}
class Tests(unittest.TestCase):
 def test_explicit_rows_only(self):
  rows=structured_rows(source()["raw_page_text"])
  self.assertEqual([(x["team"],x["player"],x["status"]) for x in rows],
                   [("BOS","John Smith","Questionable"),("NYK","Mary Jones","Out")])
 def test_candidates_not_verified_lineups(self):
  r=compile_report(S,source())
  self.assertEqual(r["official_player_rows_resolved"],2)
  self.assertFalse(r["games"]["42"]["lineups_confirmed"])
  self.assertFalse(r["games"]["42"]["official_player_team_status_confirmed"])
 def test_late_download_not_backdated(self):
  r=compile_report(S,source("2026-10-26T19:00:00Z"))
  self.assertEqual(r["official_player_rows_resolved"],0)
  self.assertFalse(r["games"]["42"]["source_time_validated"])
if __name__=="__main__":unittest.main()
