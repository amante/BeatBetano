import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nflcom_live_smoke import smoke
class Tests(unittest.TestCase):
    def test_failed_source_is_reported_not_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("nflcom_live_smoke.capture",side_effect=RuntimeError("HTTP 403")):
                out=smoke("https://www.nfl.com/injuries/league/2026/REG7",root)
            self.assertEqual(out["rows"],0)
            self.assertEqual(out["status"],"source_unavailable_or_access_restricted")
            self.assertTrue((Path(root)/"smoke_report.json").is_file())
if __name__=="__main__":unittest.main()
