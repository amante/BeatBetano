"""Preserve latest available NBA-published injury PDF and extracted lines.

Raw official document text is EVIDENCE, not independently verified player
resolution. Do not infer unlisted athletes are healthy or starting.
"""
import argparse,hashlib,io,json,re
from urllib.parse import unquote
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse
from pathlib import Path
import requests
from html.parser import HTMLParser

INDEX="https://official.nba.com/nba-injury-report-2026-27-season/"

class AnchorReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
        self.href=None
        self.label=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href")
            self.label=[]
    def handle_data(self,data):
        if self.href is not None:self.label.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            self.links.append((self.href," ".join(self.label).strip()))
            self.href=None
            self.label=[]

def discover(html):
    parsed=AnchorReader()
    parsed.feed(html)
    candidates=[]
    for href,label in parsed.links:
        url=urljoin(INDEX,href)
        host=urlparse(url).hostname or ""
        if not (host=="ak-static.cms.nba.com" and urlparse(url).path.lower().endswith(".pdf")):continue
        if "injury" not in url.lower():continue
        candidates.append({"url":url,"label":label})
    if not candidates:raise ValueError("No NBA official injury report PDF references found")
    return candidates

def report_datetime(link):
    """Recognize NBA file date+ET clock only where explicit in the filename."""
    from zoneinfo import ZoneInfo
    name=unquote(urlparse(link).path.rsplit("/",1)[-1])
    m=re.search(r"(20\d\d)[-_](\d\d)[-_](\d\d)[-_](\d{1,2})(?:[-_]?)(\d\d)(AM|PM)",name,re.I)
    if not m:return None
    year,month,day,hour,minute,ampm=m.groups()
    hour=int(hour)%12+(12 if ampm.upper()=="PM" else 0)
    try:return datetime(int(year),int(month),int(day),hour,int(minute),tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    except ValueError:return None

def select_report(entries,freeze):
    """Prefer newest explicit report timestamp that predates snapshot; never future."""
    stamped=[(report_datetime(item["url"]),item) for item in entries]
    eligible=[(dt,item) for dt,item in stamped if dt is not None and dt<=freeze]
    if not eligible:
        raise ValueError("No dated official report proven to precede prediction snapshot")
    dt,item=max(eligible,key=lambda pair:pair[0])
    return item,dt

def retrieve(snapshot,session=None):
    s=session or requests.Session()
    now=datetime.now(timezone.utc)
    r=s.get(INDEX,timeout=30);r.raise_for_status()
    entries=discover(r.text)
    freeze=datetime.fromisoformat(snapshot['created_at_utc'].replace('Z','+00:00'))
    if freeze.tzinfo is None:raise ValueError('UTC pregame snapshot required')
    chosen,report_time=select_report(entries,freeze)
    pdf=s.get(chosen["url"],timeout=40);pdf.raise_for_status()
    if not pdf.content.startswith(b"%PDF-"):raise ValueError("Official URL did not return PDF bytes")
    from pypdf import PdfReader
    pages=PdfReader(io.BytesIO(pdf.content)).pages
    if not pages:raise ValueError("Empty official injury report")
    extracted=[p.extract_text(extraction_mode="layout") or "" for p in pages]
    if not any("Injury" in x or "INJURY" in x for x in extracted):
        raise ValueError("Official report extraction missing injury text")
    return {"source_index":INDEX,"report_url":chosen["url"],
      "link_label":chosen["label"],"downloaded_at_utc":now.isoformat(),
      "pdf_sha256":hashlib.sha256(pdf.content).hexdigest(),
      "pages":len(pages),"raw_page_text":extracted,
      "source_report_as_of_utc":report_time.isoformat(),
      "report_datetime_filename_verified":True,
      "official_document_retrieved":True,
      "individual_player_status_verified":False,
      "note":"Latest indexed PDF, NOT proven published before every tipoff; no starting lineup confirmation."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True)
    args=p.parse_args()
    data=json.loads(Path(args.snapshot).read_text())
    if not data.get("predictions"):raise ValueError("No prospective fixtures")
    try:
        report=retrieve(data)
    except (requests.RequestException, ValueError, ImportError) as exc:
        report={"source_index":INDEX,"report_url":None,"official_document_retrieved":False,
                "individual_player_status_verified":False,"raw_page_text":[],
                "source_report_as_of_utc":None,
                "retrieval_status":"unavailable",
                "retrieval_error_type":type(exc).__name__,
                "note":"Official NBA source unavailable; no official athlete statuses verified. ESPN preview is separately collected as unverified observations."}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps({"report_url":report["report_url"],"pages":report.get("pages",0),
      "official_source_available":report["official_document_retrieved"],"player_status_verified":False},indent=2))
if __name__=="__main__":main()
