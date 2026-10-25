import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_injury_pdf import discover
class Tests(unittest.TestCase):
    def test_only_official_nba_static_pdf_accepted(self):
        html='<a href="https://evil.test/Injury-Report.pdf">Fake</a><a href="https://ak-static.cms.nba.com/wp-content/uploads/2026/Injury-Report_2026.pdf">NBA PDF</a>'
        r=discover(html)
        self.assertEqual(len(r),1)
        self.assertIn("ak-static.cms.nba.com",r[0]["url"])
    def test_no_report_fails(self):
        with self.assertRaisesRegex(ValueError,"No NBA official"):discover("<p>Nothing</p>")
if __name__=="__main__":unittest.main()
