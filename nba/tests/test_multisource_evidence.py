import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisource_evidence import extract_br,collect
XML=b"""<rss><channel><item><title>NBA Celtics player ruled out with ankle injury</title><link>https://bleacherreport.com/articles/12345-nba</link><pubDate>Mon, 26 Oct 2026 14:00:00 GMT</pubDate></item><item><title>NBA Lakers player ruled out</title><link>https://evil.example/unknown</link><pubDate>Mon, 26 Oct 2026 14:00:00 GMT</pubDate></item></channel></rss>"""
class Resp:
 content=XML
 def raise_for_status(self):pass
class Session:
 def get(self,*args,**kwargs):return Resp()
SNAP={"content_sha256":"abc","predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-26T22:00:00Z"}]}
class Tests(unittest.TestCase):
 def test_source_and_time(self):
  rows=extract_br(XML,"2026-10-26T17:00:00Z")
  self.assertEqual(len(rows),1);self.assertFalse(rows[0]["independent_confirmation"])
 def test_no_future_publication(self):
  self.assertEqual(extract_br(XML,"2026-10-26T13:00:00Z"),[])
 def test_espn_and_br_are_not_independent_official(self):
  espn={"games":{"1":{"supplementary_injury_observations":{"items":[{"player":"Example"}],"observed_at_utc":"2026-10-26T16:00:00Z"}}}}
  r=collect(SNAP,espn,{},Session(),observed="2026-10-26T17:00:00Z")
  self.assertEqual(len(r["games"]["1"]["espn_injury_observations"]),1)
  self.assertEqual(r["games"]["1"]["independent_sources_confirming_injury"],0)
  self.assertFalse(r["final_probabilities_authorized"])
if __name__=="__main__":unittest.main()
