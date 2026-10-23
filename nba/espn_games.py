"""Historical NBA game ingestion from public ESPN scoreboard responses.

Records completed regular-season games only; no fabricated fixtures.
HTTP and dataset validation fail closed. ESPN is an independent third-party
source; coverage and usage conditions must be reviewed prior to production.
"""
import argparse,json,time
from datetime import date,timedelta
from pathlib import Path
import requests
BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

def parse_events(payload):
    games=[]
    for event in payload.get("events",[]):
        competitions=event.get("competitions",[])
        if len(competitions)!=1:continue
        comp=competitions[0]
        teams=comp.get("competitors",[])
        if len(teams)!=2:continue
        mapping={t.get("homeAway"):t for t in teams}
        if set(mapping)!={"home","away"}:continue
        status=comp.get("status",event.get("status",{})).get("type",{})
        if not status.get("completed",False):continue
        # Reject playoff/postseason contests for regular-season benchmark.
        season_type=event.get("season",{}).get("type")
        if season_type!=2:continue
        home,away=mapping["home"],mapping["away"]
        try:
            hp=int(home["score"]);ap=int(away["score"])
            assert hp!=ap
            home_id=str(home["team"]["abbreviation"])
            away_id=str(away["team"]["abbreviation"])
            tipoff=event["date"]
            year=int(event["season"]["year"])
            eid=str(event["id"])
        except (KeyError,ValueError,TypeError,AssertionError):
            continue
        if home_id==away_id:continue
        games.append({"game_id":eid,"season":year,"tipoff_utc":tipoff,
                      "home_team":home_id,"away_team":away_id,
                      "home_points":hp,"away_points":ap})
    return games

def fetch_range(start,end,session=None):
    if start != end: raise ValueError("ESPN scoreboard requires a single day")
    s=session or requests.Session()
    r=s.get(BASE,params={"dates":f"{start:%Y%m%d}","limit":500},timeout=40)
    r.raise_for_status()
    payload=r.json()
    if not isinstance(payload.get("events"),list):
        raise ValueError("ESPN scoreboard missing events array")
    return parse_events(payload),len(payload["events"])

def ingest(out,start,end):
    start=date.fromisoformat(start);end=date.fromisoformat(end)
    if end<start:raise ValueError("Bad date window")
    # ESPN public scoreboard supports a single YYYYMMDD per request.
    cursor=start;raw=0;games=[]
    while cursor<=end:
        part,n=fetch_range(cursor,cursor)
        if n>=500:raise ValueError("Potential truncated scoreboard data")
        games+=part;raw+=n
        cursor+=timedelta(days=1)
        time.sleep(0.2)
    by_id={}
    for g in games:
        if g["game_id"] in by_id and g!=by_id[g["game_id"]]:
            raise ValueError("Conflicting duplicate game")
        by_id[g["game_id"]]=g
    values=sorted(by_id.values(),key=lambda x:(x["tipoff_utc"],x["game_id"]))
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(values,indent=2))
    audit={"start":str(start),"end":str(end),"raw_events":raw,"complete_regular_games":len(values),
           "season_counts":{str(k):sum(g["season"]==k for g in values) for k in sorted(set(g["season"] for g in values))}}
    # Preserve identifiers for source reconciliation, without silently trimming
    # a nonstandard 1230+ set to force an artificially passing backtest.
    if len(values)!=1230:
        audit["coverage_warning"]="Game count differs from canonical 1230; reconcile ESPN event classifications before scoring"
        audit["game_ids_for_reconciliation"]=[x["game_id"] for x in values]
    (p.parent/"coverage.json").write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit,indent=2))
    return values

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--output",required=True)
    x=p.parse_args();ingest(x.output,x.start,x.end)
