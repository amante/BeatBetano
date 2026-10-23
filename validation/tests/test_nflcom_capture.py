import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nflcom_capture import capture,validate_url

class Response:
    status_code=200
    headers={"Content-Type":"text/html; charset=utf-8"}
    content=b"<html><body>NFL injury report</body></html>"
class FakeSession:
    def get(self,*args,**kwargs):return Response()

class Tests(unittest.TestCase):
    def test_safe_url(self):
        validate_url("https://www.nfl.com/injuries/league/2026/REG7")
        with self.assertRaises(ValueError):validate_url("https://nfl.com.evil.test/injuries/league/2026/REG7")
    def test_raw_capture_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=capture("https://www.nfl.com/injuries/league/2026/REG7",tmp,session=FakeSession())
            self.assertEqual(m["data_status"],"raw_page_only_no_verified_player_rows")
            self.assertTrue((Path(tmp)/"capture.html").exists())
    def test_http_access_denied_fails(self):
        class Forbidden:
            status_code=403
            headers={"Content-Type":"text/html"}
            content=b""
        class Session:
            def get(self,*args,**kwargs):return Forbidden()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,"403"):
                capture("https://www.nfl.com/injuries/league/2026/REG7",tmp,session=Session())
            self.assertFalse((Path(tmp)/"capture.json").exists())
if __name__=="__main__":unittest.main()
