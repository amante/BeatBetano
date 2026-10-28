"""NHL historical team performance from prior completed dates only.

Uses official archived playerByGameStats (POSTGAME from previous games).
Measures observed goalie save percentage and skater scoring; no current-game
goalie starter, lineup prediction, PP/PK, xG or prospective roster assertions.
"""
import argparse,hashlib,json,math
from collections import defaultdict,Counter
from pathlib import Path

def number(value):
    if isinstance(value,bool) or value is None:return None
    try:
        x=float(value)
        return x if math.isfinite(x) and x>=0 else None
    except (TypeError,ValueError):return None

def extract(stats,side):
    node=stats.get(side+"Team") if isinstance(stats,dict) else None
    if not isinstance(node,dict):return {"goalies":None,"skaters":None}
    goals_saved=shots_faced=0.; goalies=0
    for goalie in node.get("goalies",[]) if isinstance(node.get("goalies"),list) else []:
        if not isinstance(goalie,dict):continue
        saves=number(goalie.get("saveShotsAgainst") if goalie.get("saveShotsAgainst") is not None else goalie.get("saves"))
        faced=number(goalie.get("shotsAgainst"))
        if faced is not None and saves is not None and faced>=saves and faced>0:
            goalies+=1; goals_saved+=saves;shots_faced+=faced
    shots=goals=0.; skaters=0
    for key in ("forwards","defense","defensemen"):
        for player in node.get(key,[]) if isinstance(node.get(key),list) else []:
            if not isinstance(player,dict):continue
            g=number(player.get("goals"));s=number(player.get("shots"))
            if g is None or s is None or g>s:continue
            goals+=g;shots+=s;skaters+=1
    return {"goalies":{"appearances":goalies,"saves":goals_saved,"shots_against":shots_faced} if goalies else None,
            "skaters":{"appearances":skaters,"goals":goals,"shots":shots} if skaters else None}

def snapshot(state):
    n=state["games"]
    goalie=state["goalie"]
    skater=state["skater"]
    return {"past_games":n,"past_goalie_observation_games":state["goalie_games"],
       "past_skater_observation_games":state["skater_games"],
       "prior_goalie_save_pct":round(goalie["saves"]/goalie["shots_against"],6) if goalie["shots_against"] else None,
       "prior_goalie_shots_against":int(goalie["shots_against"]),
       "prior_skater_goals_per_observed_game":round(skater["goals"]/state["skater_games"],6) if state["skater_games"] else None,
       "prior_skater_shots_per_observed_game":round(skater["shots"]/state["skater_games"],6) if state["skater_games"] else None,
       "pregame_starter_confirmed":False,
       "pregame_roster_confirmed":False}

def state():
    return {"games":0,"goalie_games":0,"skater_games":0,
            "goalie":{"saves":0.,"shots_against":0.},
            "skater":{"goals":0.,"shots":0.}}

def derive(archive,expected=2811):
    source=Path(archive)
    paths=sorted(p for p in source.glob("*.json") if p.name!="manifest.json")
    if len(paths)!=expected:raise ValueError(f"Expected {expected} games; found {len(paths)}")
    days=defaultdict(list);ids=set()
    for path in paths:
        game=json.loads(path.read_text())
        gid=str(game.get("game_id",""))
        if gid!=path.stem or gid in ids:raise ValueError("Bad/duplicate game ID")
        ids.add(gid)
        for k in ("date","home","away"):
            if not game.get(k):raise ValueError("Missing "+k)
        days[game["date"]].append(game)
    history=defaultdict(state);result=[];counts=Counter()
    for day in sorted(days):
        # Freeze every fixture's view before processing any outcome from day.
        for game in sorted(days[day],key=lambda r:str(r["game_id"])):
            record={"game_id":str(game["game_id"]),"date":day,
                    "home":snapshot(history[game["home"]]),
                    "away":snapshot(history[game["away"]]),
                    "source_class":"earlier_dates_postgame_boxscores_only"}
            result.append(record)
            for side in ("home","away"):
                for key in ("prior_goalie_save_pct","prior_skater_goals_per_observed_game"):
                    if record[side][key] is not None:counts[side+"_"+key]+=1
        for game in days[day]:
            stats=(game.get("boxscore") or {}).get("player_by_game_stats")
            for side in ("home","away"):
                h=history[game[side]];h["games"]+=1
                e=extract(stats,side)
                for name,count in (("goalie","goalie_games"),("skater","skater_games")):
                    v=e["goalies" if name=="goalie" else "skaters"]
                    if v is None:continue
                    h[count]+=1
                    for metric in h[name]:
                        h[name][metric]+=v[metric]
    return result,{"games":len(result),"team_sides":len(result)*2,
                   "non_null_feature_counts":dict(counts),
                   "same_game_starters_verified":0,"same_game_rosters_verified":0,
                   "odds_used":False,"model_promotion_authorized":False,
                   "goalie_stat": "shot-weighted prior-game team goalie save percentage, not selected starter",
                   "limitation":"Historical team aggregates from previous dates only. Player-level identities, pregame availability and PP/PK not established."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True);p.add_argument("--expected",type=int,default=2811)
    p.add_argument("--output",required=True);p.add_argument("--manifest",required=True)
    a=p.parse_args();data,report=derive(a.archive,a.expected)
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,indent=2))
    report["sha256"]=hashlib.sha256(output.read_bytes()).hexdigest()
    Path(a.manifest).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
