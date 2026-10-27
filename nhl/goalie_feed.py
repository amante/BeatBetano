"""Prospective goalie game-log collection from NHL public web API.

The roster identifies *candidates*, never a confirmed game starter.
All game-log samples must precede the freeze time and the game date.
"""
import argparse,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests
BASE="https://api-web.nhle.com/v1"

def utc(x):
    d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("UTC offset required")
    return d.astimezone(timezone.utc)

def read_save_line(g):
    """Read two possible official goalie game-log schemas without inventing saves."""
    shots=g.get("shotsAgainst")
    saves=g.get("saves")
    against=g.get("goalsAgainst")
    if type(shots) is not int or shots<0:
        return None
    if type(saves) is not int and type(against) is int and 0<=against<=shots:
        saves=shots-against
    if type(saves) is not int or not 0<=saves<=shots:
        return None
    if type(against) is int and shots-saves!=against:
        return None
    return shots,saves

def candidate_logs(roster,fetch_log,team,freeze,tipoff,season):
    goalie_list=roster.get("goalies",[])
    if not isinstance(goalie_list,list):raise ValueError("No goalie roster list")
    out=[]
    for goalie in goalie_list:
        pid=goalie.get("id")
        if type(pid) is not int:continue
        source=f"{BASE}/player/{pid}/game-log/{season}/2"
        try:payload=fetch_log(source)
        except (requests.RequestException,KeyError,ValueError):
            out.append({"goalie_id":str(pid),"team":team,"status":"source_unavailable","source_url":source})
            continue
        log=payload.get("gameLog",[])
        if not isinstance(log,list):continue
        records=[]; rejected=0
        for g in log:
            day=g.get("gameDate")
            if not isinstance(day,str):continue
            try:date=datetime.fromisoformat(day+"T23:59:59+00:00")
            except ValueError:continue
            if date>=utc(freeze) or date>=utc(tipoff):continue
            if g.get("gameType") not in (None,2):continue
            stat=read_save_line(g)
            if stat is None:
                rejected+=1;continue
            records.append((date,*stat))
        records.sort(reverse=True)
        recent=records[:5]
        shots=sum(x[1] for x in recent);saves=sum(x[2] for x in recent)
        starts7=sum(1 for x in records if x[0]>=utc(freeze)-timedelta(days=7))
        out.append({"goalie_id":str(pid),"team":team,"source_url":source,
          "observed_at_utc":freeze,"starter_status":"unknown","official_confirmation":False,
          "shots_against":shots,"saves":saves,"sample_games":len(recent),
          "starts_last_7_days":starts7,"gsax":None,
          "data_status":"recent_completed_games_only" if recent else ("unrecognized_game_log_stats" if rejected else "no_verified_game_logs"),
          "rejected_stat_rows":rejected})
    return out

def collect(slate,session=None):
    sess=session or requests.Session()
    fetch=lambda url:sess.get(url,timeout=25)
    def read(url):
        response=fetch(url);response.raise_for_status();return response.json()
    freeze=slate["as_of_utc"];games={}
    for g in slate["events"]:
        gid=str(g["event_id"]);pair={}
        season_start=int(g["start_utc"][:4])-(int(g["start_utc"][5:7])<7)
        season=season_start*10000+season_start+1
        for side in ("home","away"):
            team=g[side+"_team"]
            url=f"{BASE}/roster/{team}/{season}"
            try:
                roster=read(url)
                pair[side]={"roster_url":url,"candidates":candidate_logs(roster,read,team,freeze,g["start_utc"],season)}
            except (requests.RequestException,ValueError,KeyError) as e:
                pair[side]={"roster_url":url,"candidates":[],"status":"unavailable"}
        games[gid]=pair
    return {"schema_version":1,"sport":"nhl","as_of_utc":freeze,"games":games,
      "note":"Goalies from roster are candidates only; no starter confirmation or GSAx is inferred."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--slate",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();result=collect(json.loads(Path(a.slate).read_text()))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"games":len(result["games"]),
      "goalie_candidates":sum(len(x["candidates"]) for g in result["games"].values() for x in g.values())}))
if __name__=="__main__":main()
