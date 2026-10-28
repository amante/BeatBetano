"""Collect the daily five-sport scoreboard with explicitly sourced ESPN data.

Snapshots contain fixtures/results only. They are NOT model predictions.
"""
import argparse,json,urllib.request
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

TZ=ZoneInfo("America/Santiago")
FEEDS={
 "nba":[("NBA","basketball/nba")],
 "nfl":[("NFL","football/nfl")],
 "nhl":[("NHL","hockey/nhl")],
 "tennis":[("ATP","tennis/atp"),("WTA","tennis/wta")],
 "soccer":[("England","Premier League","soccer/eng.1"),
           ("Spain","La Liga","soccer/esp.1"),
           ("Italy","Serie A","soccer/ita.1"),
           ("Germany","Bundesliga","soccer/ger.1"),
           ("France","Ligue 1","soccer/fra.1"),
           ("Europe","Champions League","soccer/uefa.champions"),
           ("Chile","Primera División","soccer/chi.1"),
           ("USA","MLS","soccer/usa.1")]}
BASE="https://site.api.espn.com/apis/site/v2/sports/"

def get_json(url):
 req=urllib.request.Request(url,headers={"User-Agent":"BeatBetano Research Dashboard/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=25) as response:
  return json.load(response)

def parse_event(event,sport,country=None,league=None):
 competitions=event.get("competitions") or []
 if not competitions:return None
 comp=competitions[0]
 competitors=comp.get("competitors") or []
 home=next((x for x in competitors if x.get("homeAway")=="home"),None)
 away=next((x for x in competitors if x.get("homeAway")=="away"),None)
 if sport=="tennis" and (not home or not away) and len(competitors)>=2:
  home,away=competitors[0],competitors[1]
 if not home or not away:return None
 dt=event.get("date")
 if not dt:return None
 state=(comp.get("status") or event.get("status") or {}).get("type",{})
 status=state.get("name","unknown")
 def team(x):return (x.get("team") or {}).get("displayName") or (x.get("athlete") or {}).get("displayName") or x.get("displayName") or "Unknown"
 def score(x):
  v=x.get("score")
  if isinstance(v,dict):v=v.get("displayValue") or v.get("value")
  return str(v) if v is not None else None
 return {"id":str(event.get("id")),"sport":sport,"country":country,"league":league,
   "competition":league or sport.upper(),"home":team(home),"away":team(away),
   "start_utc":dt,"status":status,"completed":bool(state.get("completed")),
   "home_score":score(home),"away_score":score(away),
   "source":"ESPN public scoreboard","source_event_id":str(event.get("id"))}

def collect(day,fetch=get_json):
 result={"date":day,"timezone":"America/Santiago","as_of_utc":datetime.now(ZoneInfo("UTC")).isoformat(),
   "feeds":{},"games":[],"errors":[],"data_kind":"fixtures_and_results_only"}
 for sport,feeds in FEEDS.items():
  result["feeds"][sport]=[]
  for feed in feeds:
   if sport=="soccer":country,league,path=feed
   else:league,path=feed;country=None
   # Include adjacent UTC dates so late-night games are not lost for Chile.
   rows=[]
   for delta in (-1,0,1):
    d=(datetime.fromisoformat(day)+timedelta(days=delta)).strftime("%Y%m%d")
    try:
     data=fetch(BASE+path+"/scoreboard?dates="+d+"&limit=300")
     for e in data.get("events") or []:
      item=parse_event(e,sport,country,league)
      if item and datetime.fromisoformat(item["start_utc"].replace("Z","+00:00")).astimezone(TZ).date().isoformat()==day:
       rows.append(item)
    except Exception as exc:
     result["errors"].append({"sport":sport,"feed":league,"date":d,"error":str(exc)[:150]})
   unique={x["id"]:x for x in rows}
   result["games"].extend(unique.values())
   result["feeds"][sport].append({"competition":league,"country":country,
      "games":len(unique),"complete":not any(e["sport"]==sport and e["feed"]==league for e in result["errors"])})
 result["games"].sort(key=lambda x:(x["start_utc"],x["sport"],x["id"]))
 return result

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--date",default=datetime.now(TZ).date().isoformat())
 p.add_argument("--out",default="frontend/data/daily.json")
 a=p.parse_args()
 out=collect(a.date)
 prev=(datetime.fromisoformat(a.date)-timedelta(days=1)).date().isoformat()
 older=collect(prev)
 out["games"]=sorted(older["games"]+out["games"],key=lambda x:(x["start_utc"],x["sport"],x["id"]))
 out["errors"].extend(older["errors"])
 out["included_dates"]=[prev,a.date]
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({"games":len(out["games"]),"feed_errors":len(out["errors"]),"sports":list(out["feeds"])}))
if __name__=="__main__":main()
