"""Live, fail-closed smoke check of the public NFL.com injury page.

No bypassing site restrictions; no synthetic rows reported as real.
"""
import argparse,json
from pathlib import Path
from nflcom_capture import capture
from nflcom_parse import run as parse

def smoke(url,output):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    report={"url":url,"capture":"not_attempted","parse":"not_attempted","rows":0,"status":"unavailable"}
    try:
        capture(url,folder/"raw")
        report["capture"]="success"
        try:
            rows=parse(folder/"raw",folder/"injury_rows.csv")
            report["parse"]="success"
            report["rows"]=len(rows)
            report["status"]="raw_structured_rows_unmapped"
        except Exception as error:
            report["parse"]=f"unavailable: {type(error).__name__}: {error}"
            report["status"]="html_captured_but_no_verified_structured_rows"
    except Exception as error:
        report["capture"]=f"unavailable: {type(error).__name__}: {error}"
        report["status"]="source_unavailable_or_access_restricted"
    (folder/"smoke_report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--url",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();smoke(a.url,a.output)
