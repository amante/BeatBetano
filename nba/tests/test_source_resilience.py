import sys, unittest
from pathlib import Path
from unittest.mock import patch
import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_injury_pdf import main as official_main
from game_preview import collect


class RejectSession:
    def get(self,*args,**kwargs):
        raise requests.exceptions.HTTPError("403 Forbidden")


class SourceResilienceTests(unittest.TestCase):
    def test_espn_failure_is_explicit_and_does_not_remove_game(self):
        snap={"content_sha256":"abc","predictions":[
            {"game_id":"123","tipoff_utc":"2099-10-25T23:00:00Z"}]}
        out=collect(snap,session=RejectSession())
        self.assertEqual(len(out["games"]),1)
        self.assertEqual(out["games"]["123"]["retrieval_status"],"unavailable")
        self.assertIsNone(out["games"]["123"]["confirmed_starting_lineups"])

    def test_official_http_403_creates_explicit_unavailable_artifact(self):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"snapshot.json"
            out=Path(d)/"official.json"
            inp.write_text(json.dumps({"predictions":[{"game_id":"123"}]}))
            with patch("sys.argv",["official_injury_pdf.py","--snapshot",str(inp),"--output",str(out)]),patch("official_injury_pdf.retrieve",side_effect=requests.exceptions.HTTPError("403")):
                official_main()
            record=json.loads(out.read_text())
            self.assertFalse(record["official_document_retrieved"])
            self.assertEqual(record["raw_page_text"],[])
            self.assertEqual(record["retrieval_error_type"],"HTTPError")


if __name__=="__main__":
    unittest.main()
