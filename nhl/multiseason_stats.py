"""NHL REST multi-season league-wide statistics ingestion (no bookmaker inputs).

Season totals downloaded today are NOT point-in-time historical pregame inputs.
A historical backtest must use dated snapshots or per-game reconstruction.
"""
import argparse,json,time
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import requests

API="https://api.nhle.com/stats/rest/en"
REPORTS=("skater/summary","goalie/summary","team/summary")
def seasons(today,count=5):
    if not 1<=count<=10: raise ValueError("count must be 1..10")
    start=today.year-(today.month<7)
    return [f"{y}{y+1}" for y in range(start,start-count,-1)]

def extract(fetch,year,report,limit=100):
    if report not in REPORTS or not (len(year)==8 and year.isdigit()): raise ValueError("Invalid report/season")
    records=[];page=0;seen=set();maximum=3000
    while True:
        params=urlencode({"cayenneExp":f"seasonId={year} and gameTypeId=2","start":page*limit,"limit":limit})
        url=f"{API}/{report}?{params}"
        response=fetch(url)
        response.raise_for_status()
        obj=response.json()
        if not isinstance(obj,dict) or not isinstance(obj.get("data"),list):
            raise ValueError("Missing NHL Stats data array")
        batch=obj["data"]
        if not batch:break
        for entry in batch:
            if not isinstance(entry,dict):raise ValueError("Invalid NHL row")
            # NHL Stats can emit one row per player/team stint and an
            # all-teams aggregate. Player ID alone is not a unique row key.
            # Deduplicate only *identical* returned records while preserving
            # distinct team stints and season totals.
            signature=json.dumps(entry,sort_keys=True,separators=(",",":"))
            if signature in seen:
                continue
            seen.add(signature)
            records.append(entry)
        if len(records)>maximum:raise ValueError("Unexpectedly large API response")
        if len(batch)<limit:break
        page+=1
    return records

def collect(fetch,today,count=5,pause=lambda:None):
    stamp=datetime.now(timezone.utc).isoformat()
    result={"sport":"nhl","source":API,"fetched_at_utc":stamp,
      "seasons":seasons(today,count),"reports":{},"odds_used":False,
      "historical_backtest_eligible":False,
      "note":"Retrospective season totals must not be used as past pregame features."}
    for year in result["seasons"]:
        result["reports"][year]={}
        for report in REPORTS:
            try:
                data=extract(fetch,year,report)
                result["reports"][year][report]={"status":"ok" if data else "empty",
                    "count":len(data),"rows":data}
            except (requests.RequestException,ValueError) as exc:
                result["reports"][year][report]={"status":"error","count":0,
                    "error":str(exc)[:200],"rows":[]}
            pause()
    return result

def summary(result):
    lines=["## NHL Stats — Five seasons, actual league data","",
    "Current season records are descriptive. Historical season-end totals **cannot** be used as pregame snapshots.","",
    "| Season | Skaters | Goalies | Teams | Status |",
    "|---|---:|---:|---:|---|"]
    for year,items in result["reports"].items():
        vals=[items[r] for r in REPORTS]
        lines.append("| {} | {} | {} | {} | {} |".format(year,*(v["count"] for v in vals),
                 ", ".join(v["status"] for v in vals)))
    lines+=["","### Current-season sample (first five skaters)", "| Player | Team | GP | Goals | Assists | Points |","|---|---|---:|---:|---:|---:|"]
    latest=result["seasons"][0]
    for row in result["reports"][latest]["skater/summary"]["rows"][:5]:
        val=lambda k:row.get(k,"—")
        lines.append(f'| {val("skaterFullName")} | {val("teamAbbrevs")} | {val("gamesPlayed")} | {val("goals")} | {val("assists")} | {val("points")} |')
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=date.today().isoformat())
    p.add_argument("--seasons",type=int,default=5)
    p.add_argument("--output",required=True);p.add_argument("--summary",required=True)
    args=p.parse_args()
    session=requests.Session()
    report=collect(lambda url:session.get(url,timeout=25),date.fromisoformat(args.date),
                   args.seasons,lambda:time.sleep(1.5))
    for name,payload in ((args.output,json.dumps(report,indent=2)),(args.summary,summary(report))):
        path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(payload)
    counts={yr:{k:r["count"] for k,r in reports.items()} for yr,reports in report["reports"].items()}
    print(json.dumps(counts))
    current=report["reports"][report["seasons"][0]]
    if not any(v["count"]>0 for v in current.values()):
        raise SystemExit("Current NHL season returned no data; inspect Summary and artifact")

if __name__=="__main__":main()
