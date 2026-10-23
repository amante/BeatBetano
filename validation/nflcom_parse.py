"""Parse an archived NFL.com injury HTML snapshot conservatively.

Supports HTML tables with explicit Player/Position/Game Status headers.
Does NOT infer an historical publication time: inherits capture.json's
retrieval timestamp and requires a separately verified kickoff time.
"""
import argparse,json,re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

def parse_tables(html):
    soup=BeautifulSoup(html,"html.parser")
    records=[]
    for table in soup.select("table"):
        heads=[re.sub(r"\\s+"," ",x.get_text(" ",strip=True)).lower() for x in table.select("thead th")]
        if not heads:
            first=table.find("tr")
            if first: heads=[x.get_text(" ",strip=True).lower() for x in first.find_all("th")]
        def index(*aliases):
            return next((i for i,h in enumerate(heads) if h in aliases),None)
        name=index("player","name")
        pos=index("position","pos")
        status=index("game status","game designation","status")
        if None in (name,pos,status):continue
        for tr in table.select("tbody tr"):
            cells=[re.sub(r"\\s+"," ",x.get_text(" ",strip=True)) for x in tr.find_all(["td","th"],recursive=False)]
            if len(cells)<=max(name,pos,status):continue
            state=cells[status].strip().upper()
            if state not in {"OUT","DOUBTFUL","QUESTIONABLE"}:continue
            if cells[name] and cells[pos]:
                records.append({"player_name":cells[name],"position":cells[pos],"game_status":state})
    return pd.DataFrame(records,columns=["player_name","position","game_status"])

def run(capture_dir,out):
    src=Path(capture_dir)
    metadata=json.loads((src/"capture.json").read_text())
    raw=(src/"capture.html").read_bytes()
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=metadata["sha256"]:
        raise ValueError("HTML digest mismatch")
    rows=parse_tables(raw)
    if rows.empty:raise ValueError("No verifiable injury status rows; HTML may be dynamic or layout changed")
    rows["source_url"]=metadata["source_url"]
    rows["captured_at_utc"]=metadata["captured_at_utc"]
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    rows.to_csv(dest,index=False)
    print(f"Parsed {len(rows)} injury rows; team/game context still unverified")
    return rows

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--capture-dir",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.capture_dir,a.output)
