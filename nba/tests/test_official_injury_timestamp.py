import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_injury_pdf import report_datetime,select_report
class Tests(unittest.TestCase):
 def test_official_nba_filename_timestamp(self):
  self.assertEqual(report_datetime("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-26_12_00PM.pdf"),
    datetime(2026,10,26,16,0,tzinfo=timezone.utc))
 def test_report_no_future_leakage(self):
  entries=[{"url":"https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-26_12_00PM.pdf"},
           {"url":"https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-26_12_15PM.pdf"}]
  e,t=select_report(entries,datetime(2026,10,26,16,5,tzinfo=timezone.utc))
  self.assertIn("12_00PM",e["url"])
 def test_reject_unknown_time(self):
  with self.assertRaises(ValueError):select_report([{"url":"https://ak-static.cms.nba.com/injury/report.pdf"}],datetime.now(timezone.utc))
if __name__=="__main__":unittest.main()
