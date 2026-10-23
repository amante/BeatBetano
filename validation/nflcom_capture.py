"""Conservative live HTTP evidence capture of a public NFL.com injury page.

Captures fetched HTML, UTC retrieval time, SHA256, and source URL. Never
retroactively assigns capture time to the page's publication history.
Does not bypass anti-bot controls or interpret JavaScript-rendered data.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

def validate_url(url):
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in {"www.nfl.com","nfl.com"}:
        raise ValueError("Only HTTPS nfl.com is permitted")
    if not parsed.path.startswith("/injuries/league/"):
        raise ValueError("Only official NFL league injury-report pages are supported")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("Unexpected URL credentials or port")
    return url

def capture(url,output,timeout=25,session=None):
    validate_url(url)
    requester=session or requests.Session()
    response=requester.get(url,timeout=timeout,headers={"User-Agent":"BeatBetanoResearch/1.0 (public-data provenance)"},allow_redirects=False)
    if response.status_code in (301,302,303,307,308):
        raise RuntimeError("Redirect not followed; review destination manually")
    if response.status_code!=200:
        raise RuntimeError(f"NFL.com returned HTTP {response.status_code}; no bypass attempted")
    if "text/html" not in response.headers.get("Content-Type","").lower():
        raise RuntimeError("Unexpected media type; no archive created")
    if len(response.content)>5_000_000:
        raise RuntimeError("Page exceeds safe archive size")
    timestamp=datetime.now(timezone.utc).isoformat()
    digest=hashlib.sha256(response.content).hexdigest()
    dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
    (dest/"capture.html").write_bytes(response.content)
    meta={"source_url":url,"captured_at_utc":timestamp,"sha256":digest,
          "bytes":len(response.content),"http_status":response.status_code,
          "data_status":"raw_page_only_no_verified_player_rows",
          "note":"Captured time is HTTP retrieval time, not original publication time."}
    (dest/"capture.json").write_text(json.dumps(meta,indent=2))
    print(json.dumps(meta,indent=2))
    return meta

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    capture(args.url,args.output)
