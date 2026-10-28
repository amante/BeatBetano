"""Prior-date player goalie and skater metrics from audited official NHL boxscores.

Preserves player IDs, prior observed shots/saves and ice time.  Ice time is
historical POSTGAME evidence only, never current game's confirmed deployment.
"""
import argparse,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter

def seconds(v):
    if not isinstance(v,str) or ":" not in v:return None
    a=v.split(":")
    if len(a)!=2:return None
    try:m,s=map(int,a)
    except ValueError:return None
    return m*60+s if m>=0 and 0<=s<60 else None

def numeric(v):
    try:
        if isinstance(v,bool):return None
        x=int(v)
        return x if x>=0 else None
    except (ValueError,TypeError):return None

def goalie_totals(p):
    raw=p.get("saveShotsAgainst")
    if isinstance(raw,str) and "/" in raw:
        parts=raw.split("/")
        if len(parts)!=2:return None
        saves,shots=map(numeric,parts)
    else:saves,shots=numeric(raw if raw is not None else p.get("saves")),numeric(p.get("shotsAgainst"))
    return (saves,shots) if saves is not None and shots is not None and 0<shots and saves<=shots else None

def entries(stats,side):
    node=stats.get(side+"Team") if isinstance(stats,dict) else None
    if not isinstance(node,dict):return []
    result=[]
    for group in ("goalies","forwards","defense","defensemen"):
        for p in node.get(group,[]) if isinstance(node.get(group),list) else []:
            if not isinstance(p,dict) or not isinstance(p.get("playerId"),int):continue
            gid=p["playerId"];goalie=group=="goalies"
            result.append({"id":gid,"role":"goalie" if goalie else "skater",
              "toi_seconds":seconds(p.get("toi") or p.get("timeOnIce")),
              "saves_shots":goalie_totals(p) if goalie else None,
              "goals":None if goalie else numeric(p.get("goals")),
              "shots":None if goalie else numeric(p.get("sog",p.get("shots")))})
    return result

def derive(archive,expected=2811):
    paths=sorted(p for p in Path(archive).glob("*.json") if p.name!="manifest.json")
    if len(paths)!=expected:raise ValueError("Incomplete official archive")
    days=defaultdict(list);ids=set()
    for p in paths:
        g=json.loads(p.read_text());gid=str(g.get("game_id",""))
        if gid!=p.stem or gid in ids or not all(g.get(k) for k in ("date","home","away")):raise ValueError("Invalid game")
        ids.add(gid);days[g["date"]].append(g)
    histories=defaultdict(dict);out=[];coverage=Counter()
    for day in sorted(days):
        for g in sorted(days[day],key=lambda x:str(x["game_id"])):
            row={"game_id":str(g["game_id"]),"date":day,"data_class":"previous_dates_postgame_player_observations"}
            for side in ("home","away"):
                team=g[side]
                row[side]={"team":team,"players":{str(k):dict(v) for k,v in histories[team].items()}}
                for v in histories[team].values():
                    if v["goalie_shots"]:coverage["goalie_player_ids_with_prior_shots"]+=1
                    if v["toi_games"]:coverage["player_ids_with_prior_toi"]+=1
            out.append(row)
        for g in days[day]:
            stats=(g.get("boxscore") or {}).get("player_by_game_stats")
            for side in ("home","away"):
                for e in entries(stats,side):
                    h=histories[g[side]]
                    rec=h.setdefault(e["id"],{"role":e["role"],"appearances":0,"goalie_saves":0,
                        "goalie_shots":0,"goalie_games":0,"toi_seconds":0,"toi_games":0,
                        "skater_goals":0,"skater_shots":0,"skater_games":0})
                    if rec["role"]!=e["role"]:raise ValueError("Player role changed between skater/goalie")
                    rec["appearances"]+=1
                    if e["toi_seconds"] is not None:
                        rec["toi_seconds"]+=e["toi_seconds"];rec["toi_games"]+=1
                    if e["saves_shots"] is not None:
                        saves,shots=e["saves_shots"];rec["goalie_saves"]+=saves;rec["goalie_shots"]+=shots;rec["goalie_games"]+=1
                    if e["goals"] is not None and e["shots"] is not None and e["shots"]>=e["goals"]:
                        rec["skater_goals"]+=e["goals"];rec["skater_shots"]+=e["shots"];rec["skater_games"]+=1
    return out,{"games":len(out),"team_sides":2*len(out),"nonzero_prior_metric_player_side_counts":dict(coverage),
       "data_class":"retrospective past-date snapshots, not live as-of capture",
       "lineups_confirmed":0,"odds_used":False,"model_promoted":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--output",required=True);p.add_argument("--manifest",required=True)
    a=p.parse_args();rows,meta=derive(a.archive)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(rows,separators=(",",":")))
    meta["sha256"]=hashlib.sha256(dest.read_bytes()).hexdigest()
    Path(a.manifest).write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=="__main__":main()
