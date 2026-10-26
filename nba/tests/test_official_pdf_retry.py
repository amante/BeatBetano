import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_injury_pdf import eligible_reports, retrieve
BASE="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-26_"
def entry(time):return {"url":BASE+time+".pdf","label":time}
class Response:
 def __init__(self,text="",content=b"",code=200):
  self.text=text;self.content=content;self.status_code=code
 def raise_for_status(self):
  import requests
  if self.status_code>=400:
   ex=requests.HTTPError(str(self.status_code));ex.response=self;raise ex
class Fake:
 def __init__(self):self.calls=[]
 def get(self,url,timeout=0):
  self.calls.append(url)
  if "official.nba.com" in url:
   return Response(text='<a href="'+entry("12_00PM")["url"]+'">A</a><a href="'+entry("11_45AM")["url"]+'">B</a>')
  if "12_00PM" in url:return Response(code=403)
  # failure of fallback will be explicit, without pretending content is valid
  return Response(content=b"NOT PDF")
class Tests(unittest.TestCase):
 def test_orders_reports_not_later_than_cutoff(self):
  x=eligible_reports([entry("12_15PM"),entry("11_45AM"),entry("12_00PM")],
     datetime(2026,10,26,16,5,tzinfo=timezone.utc))
  self.assertEqual([v["label"] for v in x],["12_00PM","11_45AM"])
 def test_fallback_is_attempted_and_error_has_http(self):
  with self.assertRaisesRegex(ValueError,"403") as ctx:
   retrieve({"created_at_utc":"2026-10-26T14:00:00Z"},Fake())
  self.assertIn("403",str(ctx.exception))
 def test_no_future_pdfs(self):
  self.assertEqual(eligible_reports([entry("12_15PM")],
    datetime(2026,10,26,16,0,tzinfo=timezone.utc)),[])
if __name__=="__main__":unittest.main()
