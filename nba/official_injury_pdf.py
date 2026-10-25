"""Preserve latest available NBA-published injury PDF and extracted lines.

Raw official document text is EVIDENCE, not independently verified player
resolution. Do not infer unlisted athletes are healthy or starting.
"""
import argparse,hashlib,io,json,re
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

def retrieve(snapshot,session=None):
    s=session or requests.Session()
    now=datetime.now(timezone.utc)
    r=s.get(INDEX,timeout=30);r.raise_for_status()
    entries=discover(r.text)
    # NBA lists recent reports first; avoid deriving publication timestamp
    # from an ambiguous localized hyperlink label.
    chosen=entries[0]
    pdf=s.get(chosen["url"],timeout=40);pdf.raise_for_status()
    if not pdf.content.startswith(b"%PDF-"):raise ValueError("Official URL did not return PDF bytes")
    from pypdf import PdfReader
    pages=PdfReader(io.BytesIO(pdf.content)).pages
    if not pages:raise ValueError("Empty official injury report")
    extracted=[p.extract_text() or "" for p in pages]
    if not any("Injury" in x or "INJURY" in x for x in extracted):
        raise ValueError("Official report extraction missing injury text")
    return {"source_index":INDEX,"report_url":chosen["url"],
      "link_label":chosen["label"],"downloaded_at_utc":now.isoformat(),
      "pdf_sha256":hashlib.sha256(pdf.content).hexdigest(),
      "pages":len(pages),"raw_page_text":extracted,
      "source_report_as_of_utc":None,
      "official_document_retrieved":True,
      "individual_player_status_verified":False,
      "note":"Latest indexed PDF, NOT proven published before every tipoff; no starting lineup confirmation."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True)
    args=p.parse_args()
    data=json.loads(Path(args.snapshot).read_text())
    if not data.get("predictions"):raise ValueError("No prospective fixtures")
    report=retrieve(data)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:json.dump(report,f,indent=2)
    print(json.dumps({"report_url":report["report_url"],"pages":report["pages"],
      "player_status_verified":False},indent=2))
if __name__=="__main__":main()
