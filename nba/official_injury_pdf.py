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
from official_injury_table import extract as extract_official_rows
from official_injury_table import extract_team_submissions

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

def eligible_reports(entries, cutoff):
    ranked=[(report_datetime(e["url"]),e) for e in entries]
    return [entry for stamp,entry in sorted(
        ((stamp,entry) for stamp,entry in ranked if stamp is not None and stamp<=cutoff),
        key=lambda pair:pair[0],reverse=True)]

def retrieve(snapshot,session=None,report_url=None):
    s=session or requests.Session()
    now=datetime.now(timezone.utc)
    if report_url:
        parsed=urlparse(report_url)
        if (parsed.scheme!="https" or parsed.hostname!="ak-static.cms.nba.com"
                or not parsed.path.lower().endswith(".pdf")):
            raise ValueError("Direct report must be an NBA-hosted HTTPS PDF")
        entries=[{"url":report_url,"label":"NBA official PDF provided to workflow"}]
    else:
        r=s.get(INDEX,timeout=(10,20));r.raise_for_status()
        entries=discover(r.text)
    freeze=datetime.fromisoformat(snapshot['created_at_utc'].replace('Z','+00:00'))
    if freeze.tzinfo is None:raise ValueError('UTC pregame snapshot required')
    # Evidence is collected after the snapshot: select what exists NOW, never backdate it.
    choices=eligible_reports(entries,now)
    if not choices:raise ValueError("No timestamped official report <= collection time")
    failures=[]
    chosen=None
    for choice in choices[:3]:
        try:
            pdf=s.get(choice["url"],timeout=(10,20))
            pdf.raise_for_status()
            if not pdf.content.startswith(b"%PDF-"):
                raise ValueError("Official link did not return PDF bytes")
            chosen=choice
            report_time=report_datetime(chosen["url"])
            break
        except (requests.RequestException,ValueError) as exc:
            failures.append({"url":choice["url"],"type":type(exc).__name__,
                "http_status":getattr(getattr(exc,"response",None),"status_code",None)})
    if chosen is None:
        raise ValueError("PDF candidates failed: "+json.dumps(failures))
    from pypdf import PdfReader
    pages=PdfReader(io.BytesIO(pdf.content)).pages
    if not pages:raise ValueError("Empty official injury report")
    extraction_attempts=[]
    best=None
    # pypdf's layout mode preserves columns for some league PDFs, while its
    # default mode joins split table cells better in others. Try both and keep
    # the one yielding the largest auditable set of player rows.
    for text_mode in ("layout","plain"):
        if text_mode=="layout":
            page_text=[p.extract_text(extraction_mode="layout") or "" for p in pages]
        else:
            page_text=[p.extract_text() or "" for p in pages]
        if not any("Injury" in x or "INJURY" in x for x in page_text):
            extraction_attempts.append({"text_mode":text_mode,"rows":0,"error":"injury_text_missing"})
            continue
        try:
            structured=extract_official_rows(page_text,continuous_table=True)
            parse_mode="continuous_table"
        except ValueError:
            structured=extract_official_rows(page_text)
            parse_mode="page_local_conservative"
        structured=list({(row["game_date"],row["matchup"],row["team"],row["player"],row["status"]):row
                        for row in structured}.values())
        extraction_attempts.append({"text_mode":text_mode,"parse_mode":parse_mode,"rows":len(structured)})
        if best is None or len(structured)>len(best[1]):
            best=(page_text,structured,parse_mode,text_mode)
    if best is None:
        raise ValueError("Could not extract injury text from official PDF: "+json.dumps(extraction_attempts))
    extracted,structured,parse_mode,text_mode=best
    submissions=extract_team_submissions(extracted)
    return {"source_index":INDEX,"report_url":chosen["url"],
      "link_label":chosen["label"],"downloaded_at_utc":datetime.now(timezone.utc).isoformat(),
      "pdf_sha256":hashlib.sha256(pdf.content).hexdigest(),
      "pages":len(pages),"raw_page_text":extracted,
      "source_report_as_of_utc":report_time.isoformat(),
      "report_datetime_filename_verified":True,
      "official_document_retrieved":True,
      "structured_player_rows":structured,
      "team_report_statuses":submissions,
      "structured_parse_mode":parse_mode,
      "structured_text_mode":text_mode,
      "structured_parse_attempts":extraction_attempts,
      "structured_parse_status":"complete" if structured else "no_player_rows",
      "structured_parse_candidate_rows":len(structured),
      "individual_player_status_verified":False,
      "note":"Separate later evidence observation: cannot retroactively change frozen predictions; only usable before each tipoff."}

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
                "structured_player_rows":[],"team_report_statuses":[],
                "source_report_as_of_utc":None,
                "retrieval_status":"unavailable",
                "retrieval_error_type":type(exc).__name__,
                "retrieval_error_detail":str(exc)[:2000],
                "retrieval_http_status":getattr(getattr(exc,"response",None),"status_code",None),
                "note":"Official NBA source unavailable; no official athlete statuses verified. ESPN preview is separately collected as unverified observations."}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps({"report_url":report["report_url"],"pages":report.get("pages",0),
      "official_source_available":report["official_document_retrieved"],
      "structured_candidate_rows":report.get("structured_parse_candidate_rows",0),
      "teams_not_yet_submitted":len(report.get("team_report_statuses",[])),
      "error_type":report.get("retrieval_error_type"),
      "error_detail":report.get("retrieval_error_detail"),
      "http_status":report.get("retrieval_http_status"),"player_status_verified":False},indent=2))
if __name__=="__main__":main()
