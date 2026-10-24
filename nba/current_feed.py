"""Read ESPN's current NBA regular-season scoreboard as verified fixture input.

Do not pass games at/after tipoff to pregame snapshot creation. This module
does NOT fetch a multi-season completed-game history or publish predictions.
"""
import argparse,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from espn_games import BASE

def parse_current(payload,now):
    if not isinstance(payload.get("events"),list):raise ValueError("Missing scoreboard events")
    current=datetime.fromisoformat(now.replace("Z","+00:00"))
    if current.tzinfo is None or current.utcoffset()!=timedelta(0):raise ValueError("Explicit UTC now required")
    future=[];completed=[];seen=set()
    for event in payload["events"]:
        if event.get("season",{}).get("type")!=2:continue
        comps=event.get("competitions",[])
        if len(comps)!=1:continue
        homeaway={t.get("homeAway"):t for t in comps[0].get("competitors",[])}
        if set(homeaway)!={"home","away"}:continue
        try:
            gid=str(event["id"]);season=int(event["season"]["year"])
            kickoff=datetime.fromisoformat(event["date"].replace("Z","+00:00"))
            if kickoff.tzinfo is None:raise ValueError("Missing UTC kickoff")
            kickoff=kickoff.astimezone(timezone.utc)
            home=str(homeaway["home"]["team"]["abbreviation"])
            away=str(homeaway["away"]["team"]["abbreviation"])
        except (KeyError,ValueError,TypeError):continue
        if not gid or not home or not away or home==away:continue
        if gid in seen:raise ValueError("Duplicate ESPN game ID")
        seen.add(gid)
        row={"game_id":gid,"season":season,"tipoff_utc":kickoff.isoformat().replace("+00:00","Z"),
             "home_team":home,"away_team":away,"home_points":None,"away_points":None}
        status=comps[0].get("status",event.get("status",{})).get("type",{})
        if status.get("completed",False):
            try:
                row["home_points"]=int(homeaway["home"]["score"])
                row["away_points"]=int(homeaway["away"]["score"])
            except (ValueError,KeyError,TypeError):continue
            if row["home_points"]==row["away_points"]:raise ValueError("Completed NBA game tied")
            completed.append(row)
        elif kickoff>current and status.get("state")=="pre":
            future.append(row)
    return {"future_fixtures":sorted(future,key=lambda x:x["tipoff_utc"]),
            "completed_games":sorted(completed,key=lambda x:x["tipoff_utc"]),
            "as_of_utc":current.isoformat(),"source":"ESPN scoreboard; independent classification audit required"}

def fetch_day(day,now,session=None):
    if session is None:
        session=requests.Session()
        session.mount("https://",HTTPAdapter(max_retries=Retry(total=4,backoff_factor=1,
          status_forcelist=[429,500,502,503,504],allowed_methods=frozenset(["GET"]))))
    response=session.get(BASE,params={"dates":day.replace("-",""),"seasontype":2,"limit":500},timeout=40)
    response.raise_for_status()
    return parse_current(response.json(),now)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True,help="ESPN scoreboard US calendar date")
    p.add_argument("--timestamp",required=True,help="Snapshot time in UTC")
    p.add_argument("--output",required=True)
    x=p.parse_args()
    result=fetch_day(x.date,x.timestamp)
    out=Path(x.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({"future":len(result["future_fixtures"]),
                      "completed":len(result["completed_games"]),"as_of_utc":result["as_of_utc"]}))
