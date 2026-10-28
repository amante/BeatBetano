"""Previous-date-only NHL postgame roster/goalie observation coverage.

These features describe historical appearances, NOT confirmed starters,
injury status or prospective line combinations. No predictions are made.
"""
import argparse,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter

def roster_count(stats,side):
    part=(stats or {}).get(side+"Team") if isinstance(stats,dict) else None
    if not isinstance(part,dict):return None,None
    count=0;goalies=None
    for key,value in part.items():
        if not isinstance(value,list):continue
        if key=="goalies":goalies=len(value)
        if key in ("goalies","forwards","defense","defensemen"):
            count+=len(value)
    return count if count else None,goalies

def generate(folder,expected=2811):
    folder=Path(folder)
    files=sorted(p for p in folder.glob("*.json") if p.name!="manifest.json")
    if len(files)!=expected:raise ValueError(f"Expected {expected} games, got {len(files)}")
    by_day=defaultdict(list);seen=set()
    for p in files:
        x=json.loads(p.read_text())
        gid=str(x.get("game_id",""))
        if not gid or gid!=p.stem or gid in seen:raise ValueError("Duplicate/incorrect game ID")
        seen.add(gid)
        if not x.get("date") or not x.get("home") or not x.get("away"):raise ValueError("Missing fixture identity")
        by_day[x["date"]].append(x)
    history=defaultdict(lambda:{"games":0,"roster_recorded":0,"goalie_recorded":0})
    records=[]
    for day in sorted(by_day):
        # No match on this calendar date can supply features to another match today.
        for x in sorted(by_day[day],key=lambda g:str(g["game_id"])):
            prev={}
            for side in ("home","away"):
                team=x[side]
                prior=history[team]
                prev[side]={"team":team,"prior_games":prior["games"],
                    "prior_roster_observation_games":prior["roster_recorded"],
                    "prior_goalie_observation_games":prior["goalie_recorded"]}
            records.append({"game_id":str(x["game_id"]),"date":day,
                "previous_date_only":True,"home":prev["home"],"away":prev["away"],
                "same_game_starter_confirmed":False,
                "same_game_roster_verified":False,
                "pregame_pp_pk_verified":False})
        for x in by_day[day]:
            stats=(x.get("boxscore") or {}).get("player_by_game_stats")
            for side in ("home","away"):
                players,goalies=roster_count(stats,side)
                track=history[x[side]]
                track["games"]+=1
                if players is not None:track["roster_recorded"]+=1
                if goalies is not None and goalies>0:track["goalie_recorded"]+=1
    if len(records)!=expected:raise ValueError("Incorrect output count")
    count=Counter()
    for r in records:
        for side in ("home","away"):
            v=r[side]
            if v["prior_games"]:count["team_sides_with_history"]+=1
            if v["prior_goalie_observation_games"]:count["team_sides_with_prior_goalie_observations"]+=1
            if v["prior_roster_observation_games"]:count["team_sides_with_prior_roster_observations"]+=1
    return records,{"games":len(records),"total_team_sides":len(records)*2,
      "coverage":dict(count),"same_game_goalie_starter_confirmed":0,
      "same_game_roster_confirmed":0,"special_teams_pregame_verified":0,
      "information_rule":"Past completed-game observations by earlier DATE, not historical as-of snapshots",
      "outcomes_used_as_same_game_features":False,"odds_used":False,
      "full_nhl_challenger_implemented":False,"model_promotion_authorized":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True);p.add_argument("--expected",type=int,default=2811)
    p.add_argument("--output",required=True);p.add_argument("--manifest",required=True)
    args=p.parse_args()
    records,report=generate(args.archive,args.expected)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(records,indent=2))
    report["data_sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
    Path(args.manifest).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
