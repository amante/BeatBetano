"""Validate NFL.com injury-report evidence captured before kickoff.

Evidence records must be captured with trusted timestamp, source URL and
explicit event/game identity. Historic pages retrieved today do not prove
the contents were present before a 2025 game. This module does not scrape
NFL.com or assume current web content was known at historical kickoff.
"""
import argparse,json
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd

REQUIRED={"game_id","team","player_name","position","game_status",
          "source_url","captured_at_utc","kickoff_utc"}
ALLOWED={"OUT","DOUBTFUL","QUESTIONABLE","UNSPECIFIED"}
def validate(frame):
    missing=REQUIRED-set(frame.columns)
    if missing:raise ValueError(f"Missing fields: {sorted(missing)}")
    d=frame.copy()
    if d[list(REQUIRED)].isna().any().any():raise ValueError("Incomplete NFL.com evidence")
    hosts=d.source_url.map(lambda u:(urlparse(str(u)).hostname or "").lower())
    if not hosts.isin(["nfl.com","www.nfl.com"]).all():
        raise ValueError("Source URL must be on nfl.com")
    d["captured_at_utc"]=pd.to_datetime(d.captured_at_utc,utc=True,errors="raise")
    d["kickoff_utc"]=pd.to_datetime(d.kickoff_utc,utc=True,errors="raise")
    if (d.captured_at_utc>=d.kickoff_utc).any():
        raise ValueError("NFL.com historical evidence must have pre-kickoff capture")
    d["game_status"]=d.game_status.astype(str).str.upper().str.strip()
    if not d.game_status.isin(ALLOWED).all():
        raise ValueError("Unsupported game status; keep official inactives separate")
    d=d.sort_values("captured_at_utc").drop_duplicates(
        ["game_id","team","player_name"],keep="last")
    d["listed_out"]=d.game_status.eq("OUT")
    d["confirmed_inactive"]=pd.NA  # An injury-game designation is not an official inactive list.
    return d

def run(source,output):
    result=validate(pd.read_csv(source,low_memory=False))
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    result.to_csv(out/"validated_nflcom_evidence.csv",index=False)
    report={"eligible_records":len(result),"games":int(result.game_id.nunique()),
            "status":"evidence_only_no_confirmed_inactive_or_starter_identity"}
    (out/"summary.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.source,a.output)
