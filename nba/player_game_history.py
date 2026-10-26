"""Archive real ESPN completed-game player boxscore evidence.

Postgame minutes / DNP are outcomes, never point-in-time pregame injury
reports or causal injury effects. Only complete event IDs from a supplied
history ledger are accepted. The caller controls authorized source access.
"""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
import requests

SUMMARY="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

def parse_boxscore(payload,game,observed_at):
    header=payload.get("header",{})
    comps=header.get("competitions",[]) if isinstance(header,dict) else []
    if not comps or str(comps[0].get("id"))!=str(game["game_id"]):
        raise ValueError("ESPN event ID mismatch")
    competitors=comps[0].get("competitors",[])
    status=comps[0].get("status",{})
    if not (isinstance(status,dict) and status.get("type",{}).get("completed") is True):
        raise ValueError("Not a completed game")
    teams={c.get("team",{}).get("abbreviation") for c in competitors}
    if teams!={game["home_team"],game["away_team"]}:
        raise ValueError("ESPN boxscore team mismatch")
    box=payload.get("boxscore",{}).get("players",[])
    if not isinstance(box,list) or len(box)!=2:
        raise ValueError("Missing full two-team ESPN player boxscore")
    rows=[]
    for group in box:
        team=group.get("team",{}).get("abbreviation")
        if team not in teams:raise ValueError("Boxscore team mismatch")
        for block in group.get("statistics",[]):
            labels=block.get("labels",[])
            if not isinstance(labels,list):continue
            minute_col=next((i for i,x in enumerate(labels) if str(x).upper() in ("MIN","MINUTES")),None)
            for row in block.get("athletes",[]):
                athlete=row.get("athlete",{})
                pid=str(athlete.get("id",""))
                if not pid or pid=="None":continue
                stats=row.get("stats",[])
                value=stats[minute_col] if minute_col is not None and minute_col<len(stats) else None
                minutes=None
                if isinstance(value,(int,float)):
                    minutes=float(value)
                elif isinstance(value,str) and re.fullmatch(r"\d{1,2}:\d{2}",value):
                    mm,ss=map(int,value.split(":"))
                    if ss>=60:raise ValueError("Bad seconds")
                    minutes=round(mm+ss/60,3)
                elif isinstance(value,str) and re.fullmatch(r"\d{1,2}:\d{2}",value):
                    minutes=float(value)
                if minutes is not None and not 0<=minutes<=65:raise ValueError("Invalid minutes")
                rows.append({"game_id":str(game["game_id"]),"team":team,
                    "player_id":pid,"player":athlete.get("displayName"),
                    "minutes_played":minutes,
                    "did_not_play":bool(row.get("didNotPlay",False)),
                    "starter_reported_postgame":row.get("starter") if type(row.get("starter")) is bool else None,
                    "availability_known_pregame":False,
                    "observed_at_utc":observed_at})
    if not rows:raise ValueError("No individual player statistics")
    ids=[(r["team"],r["player_id"]) for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate player/team")
    return rows

def collect(games,session=None):
    if not isinstance(games,list) or not games:raise ValueError("Historical games required")
    client=session or requests.Session()
    out=[];errors=[]
    for game in games:
        if not {"game_id","home_team","away_team","tipoff_utc"}<=game.keys():
            raise ValueError("Incomplete historical fixture")
        eid=str(game["game_id"])
        now=datetime.now(timezone.utc).isoformat()
        try:
            resp=client.get(SUMMARY,params={"event":eid},timeout=30)
            resp.raise_for_status()
            out.extend(parse_boxscore(resp.json(),game,now))
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            errors.append({"game_id":eid,"error_type":type(exc).__name__})
    return {"schema_version":1,"source":SUMMARY,"games_requested":len(games),
        "games_with_player_rows":len({r["game_id"] for r in out}),
        "players":out,"unavailable_games":errors,
        "fit_for_pregame_availability":False,
        "note":"Postgame observations only. Historical pre-tipoff injury snapshots and independently validated team context remain necessary."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--limit",type=int,default=50)
    args=p.parse_args()
    games=json.loads(Path(args.history).read_text())
    if not 1<=args.limit<=250:raise ValueError("Limit must be 1..250")
    result=collect(games[-args.limit:])
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"requested":result["games_requested"],
       "with_player_rows":result["games_with_player_rows"],
       "unavailable":len(result["unavailable_games"])}))

if __name__=="__main__":
    main()
