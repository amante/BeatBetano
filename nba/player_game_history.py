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

def _season_end_year(game):
    tipoff=str(game.get("tipoff_utc") or "")
    match=re.match(r"(\\d{4})-(\\d{2})",tipoff)
    if not match:raise ValueError("Invalid historical tipoff date")
    year,month=map(int,match.groups())
    return year+1 if month>=10 else year

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
            columns={str(label).strip().upper():i for i,label in enumerate(labels)}
            minute_col=next((columns[x] for x in ("MIN","MINUTES") if x in columns),None)
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
                elif isinstance(value,str) and re.fullmatch(r"\d{1,2}(?:\.\d+)?",value):
                    minutes=float(value)
                if minutes is not None and not 0<=minutes<=65:raise ValueError("Invalid minutes")
                # Capture box-score events needed for a transparent bench profile.
                # Raw made-attempted pairs are parsed only when the provider gives
                # an explicit integer pair; absent fields remain null.
                counting={"points":("PTS","POINTS"),"rebounds":("REB","REBOUNDS"),
                          "assists":("AST","ASSISTS"),"turnovers":("TO","TOV","TURNOVERS"),
                          "steals":("STL","STEALS"),"blocks":("BLK","BLOCKS"),
                          "offensive_rebounds":("OREB","OFFENSIVE REBOUNDS"),
                          "defensive_rebounds":("DREB","DEFENSIVE REBOUNDS")}
                numeric={}
                for key,names in counting.items():
                    col=next((columns[name] for name in names if name in columns),None)
                    raw=stats[col] if col is not None and col<len(stats) else None
                    if isinstance(raw,int) and raw>=0:numeric[key]=raw
                    elif isinstance(raw,str) and re.fullmatch(r"\d+",raw.strip()):numeric[key]=int(raw)
                    else:numeric[key]=None
                pair_columns={"field_goals":("FG","FGM-A","FIELD GOALS"),
                              "three_points":("3PT","3P","3PT FG"),
                              "free_throws":("FT","FTM-A","FREE THROWS")}
                for prefix,names in pair_columns.items():
                    col=next((columns[name] for name in names if name in columns),None)
                    raw=stats[col] if col is not None and col<len(stats) else None
                    match=re.fullmatch(r"\s*(\d+)\s*[-–]\s*(\d+)\s*",str(raw)) if raw is not None else None
                    numeric[prefix+"_made"]=int(match.group(1)) if match else None
                    numeric[prefix+"_attempted"]=int(match.group(2)) if match else None
                plus_col=next((columns[name] for name in ("+/-","PLUS/MINUS","PLUS MINUS") if name in columns),None)
                plus_raw=stats[plus_col] if plus_col is not None and plus_col<len(stats) else None
                if type(plus_raw) is int:
                    numeric["plus_minus"]=plus_raw
                elif isinstance(plus_raw,str) and re.fullmatch(r"[+-]?\d+",plus_raw.strip()):
                    numeric["plus_minus"]=int(plus_raw)
                else:
                    numeric["plus_minus"]=None
                rows.append({"game_id":str(game["game_id"]),"team":team,
                    "tipoff_utc":game["tipoff_utc"],
                    "season_end_year":_season_end_year(game),
                    "opponent_team":game["away_team"] if team==game["home_team"] else game["home_team"],
                    "is_home":team==game["home_team"],
                    "player_id":pid,"player":athlete.get("displayName"),
                    "minutes_played":minutes,
                    **numeric,
                    "did_not_play":bool(row.get("didNotPlay",False)),
                    "starter_reported_postgame":row.get("starter") if type(row.get("starter")) is bool else None,
                    "availability_known_pregame":False,
                    "observed_at_utc":observed_at})
    if not rows:raise ValueError("No individual player statistics")
    ids=[(r["team"],r["player_id"]) for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate player/team")
    return rows

def collect(games,session=None,cache_dir=None):
    if not isinstance(games,list) or not games:raise ValueError("Historical games required")
    client=session or requests.Session()
    out=[];errors=[]
    for game in games:
        if not {"game_id","home_team","away_team","tipoff_utc"}<=game.keys():
            raise ValueError("Incomplete historical fixture")
        eid=str(game["game_id"])
        if cache_dir is not None:
            from observation_cache import read, save
            cached=read(cache_dir,game)
            if cached is not None:
                for row in cached:
                    team=row.get("team")
                    if team in (game["home_team"],game["away_team"]):
                        row.setdefault("season_end_year",_season_end_year(game))
                        row.setdefault("opponent_team",game["away_team"] if team==game["home_team"] else game["home_team"])
                        row.setdefault("is_home",team==game["home_team"])
                out.extend(cached)
                continue
        try:
            resp=client.get(SUMMARY,params={"event":eid},timeout=30)
            resp.raise_for_status()
            players=parse_boxscore(resp.json(),game,datetime.now(timezone.utc).isoformat())
            if cache_dir is not None:save(cache_dir,game,players)
            out.extend(players)
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
    p.add_argument("--cache-dir")
    args=p.parse_args()
    games=json.loads(Path(args.history).read_text())
    if not 1<=args.limit<=250:raise ValueError("Limit must be 1..250")
    result=collect(games[-args.limit:],cache_dir=args.cache_dir)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"requested":result["games_requested"],
       "with_player_rows":result["games_with_player_rows"],
       "unavailable":len(result["unavailable_games"])}))

if __name__=="__main__":
    main()
