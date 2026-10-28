"""Research NHL roster-aware foundation: date-lagged player observations + lineup snapshot.

No inferred future starters or predicted NHL win probabilities. Player statistics
originate in official past-game boxscores; expected lineup requires explicit
timestamped external input. No market odds.
"""
import argparse,json,hashlib
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

def player_rows(game,side):
    node=((game.get("boxscore") or {}).get("player_by_game_stats") or {}).get(side+"Team")
    if not isinstance(node,dict):return []
    out=[]
    for group in ("forwards","defense","defensemen","goalies"):
        for p in node.get(group,[]) if isinstance(node.get(group),list) else []:
            if not isinstance(p,dict):continue
            pid=p.get("playerId")
            if not isinstance(pid,int) or pid<=0:continue
            try:goals=int(p.get("goals",0)) if group!="goalies" else None
            except (ValueError,TypeError):goals=None
            try:shots=int(p.get("sog",p.get("shots",0))) if group!="goalies" else None
            except (ValueError,TypeError):shots=None
            if goals is not None and (goals<0 or shots is None or shots<goals):goals=shots=None
            out.append({"id":pid,"role":"goalie" if group=="goalies" else "skater",
                        "goals":goals,"shots":shots})
    return out

def snapshots(folder,expected=2811):
    files=sorted(p for p in Path(folder).glob("*.json") if p.name!="manifest.json")
    if len(files)!=expected:raise ValueError(f"Expected {expected} source games; got {len(files)}")
    days=defaultdict(list);seen=set()
    for p in files:
        g=json.loads(p.read_text());gid=str(g.get("game_id",""))
        if gid!=p.stem or gid in seen or not all(g.get(k) for k in ("date","home","away")):
            raise ValueError("Historical fixture identity mismatch")
        seen.add(gid);days[g["date"]].append(g)
    hist=defaultdict(lambda:defaultdict(lambda:{"appearances":0,"observed":0,"goals":0,"shots":0,"role":None}))
    output=[];coverage=0
    for day in sorted(days):
        # Freeze all games from the same date before applying any of their boxscores.
        for g in sorted(days[day],key=lambda x:str(x["game_id"])):
            entry={"game_id":str(g["game_id"]),"date":day,"source_class":"past_dates_only_postgame_player_observations"}
            for side in ("home","away"):
                team=g[side]
                entry[side]={"team":team,"players":{str(pid):dict(values) for pid,values in sorted(hist[team].items())}}
                if hist[team]:coverage+=1
            output.append(entry)
        for g in days[day]:
            for side in ("home","away"):
                for row in player_rows(g,side):
                    p=hist[g[side]][row["id"]]
                    p["appearances"]+=1;p["role"]=row["role"]
                    if row["goals"] is not None:
                        p["observed"]+=1;p["goals"]+=row["goals"];p["shots"]+=row["shots"]
    return output,{"games":len(output),"team_sides":len(output)*2,"sides_with_prior_player_identities":coverage,
                   "same_date_information_used":False,"current_lineups_known":False,
                   "odds_used":False,"official_model_promoted":False}

def score_expected_roster(past,expected,prediction_timestamp):
    """A descriptive weighted historic production score; never a game forecast."""
    stamp=datetime.fromisoformat(prediction_timestamp.replace("Z","+00:00"))
    asof=datetime.fromisoformat(expected["as_of"].replace("Z","+00:00"))
    if stamp.tzinfo is None or asof.tzinfo is None or asof>stamp:raise ValueError("Invalid lineup as-of timestamp")
    if not expected.get("source"):raise ValueError("Expected lineup must include source")
    if not isinstance(expected.get("players"),list) or not expected["players"]:
        raise ValueError("No expected players")
    ids=set();sumweight=weighted=0.;missing=[]
    for player in expected["players"]:
        pid=str(player["player_id"])
        if pid in ids:raise ValueError("Duplicate player ID")
        ids.add(pid)
        weight=player.get("weight")
        if not isinstance(weight,(int,float)) or isinstance(weight,bool) or not 0<weight<=1:
            raise ValueError("Invalid explicit lineup weight")
        if player.get("status") not in ("confirmed","projected"):
            raise ValueError("Lineup status must be confirmed or projected")
        v=past["players"].get(pid)
        if not v or v["observed"]==0:missing.append(pid);continue
        sumweight+=weight;weighted+=weight*v["goals"]/v["observed"]
    return {"score_goals_per_observed_player_game":round(weighted/sumweight,6) if sumweight else None,
            "known_weight":round(sumweight,6),"missing_player_ids":missing,
            "as_of":expected["as_of"],"lineup_source":expected["source"],
            "interpretation":"Descriptive roster-weighted past goals, NOT expected team goals, CRS rating or ML/RT/+3 probabilities"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True)
    p.add_argument("--output",required=True);p.add_argument("--manifest",required=True)
    a=p.parse_args();rows,report=snapshots(a.archive)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(rows,separators=(",",":")))
    report["sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
    Path(a.manifest).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=="__main__":main()
