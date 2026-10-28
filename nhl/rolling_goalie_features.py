"""Research-only NHL past-date rolling goalie rates with prior shrinkage.

All games on the same calendar date see the identical previous-date history.
Observations represent team goalies in completed games, not confirmed starters.
"""
import argparse,hashlib,json
from pathlib import Path
from collections import defaultdict,deque,Counter
from prior_player_goalie_stats import extract

def derive(folder,expected=2811,windows=(3,5,10),prior_shots=100,prior_rate=.905):
    if not 0<prior_rate<1 or prior_shots<0:raise ValueError("Invalid shrinkage prior")
    files=sorted(x for x in Path(folder).glob("*.json") if x.name!="manifest.json")
    if len(files)!=expected:raise ValueError("Wrong source count")
    byday=defaultdict(list);ids=set()
    for p in files:
        g=json.loads(p.read_text());gid=str(g.get("game_id",""))
        if gid!=p.stem or gid in ids or not all(g.get(k) for k in ("date","home","away")):raise ValueError("Invalid fixture")
        ids.add(gid);byday[g["date"]].append(g)
    hist=defaultdict(list);rows=[];coverage=Counter()
    for day in sorted(byday):
        for g in sorted(byday[day],key=lambda x:str(x["game_id"])):
            out={"game_id":str(g["game_id"]),"date":day,"source_class":"previous_date_goalie_team_observations"}
            for side in ("home","away"):
                x=hist[g[side]];feat={}
                for w in windows:
                    valid=x[-w:]
                    saves=sum(z[0] for z in valid);shots=sum(z[1] for z in valid)
                    name=f"goalie_last_{w}"
                    feat[name]={"observed_games":len(valid),"shots_against":int(shots),
                        "save_pct":round(saves/shots,6) if shots else None,
                        "shrunk_save_pct":round((saves+prior_shots*prior_rate)/(shots+prior_shots),6) if shots+prior_shots else None}
                    if shots:coverage[name]+=1
                feat["pregame_starter_confirmed"]=False
                out[side]=feat
            rows.append(out)
        for g in byday[day]:
            stats=(g.get("boxscore") or {}).get("player_by_game_stats")
            for side in ("home","away"):
                goalie=extract(stats,side)["goalies"]
                if goalie and goalie["shots_against"]>0:
                    hist[g[side]].append((goalie["saves"],goalie["shots_against"]))
    return rows,{"games":len(rows),"team_sides":2*len(rows),
        "coverage_nonzero_shots":dict(coverage),"windows":list(windows),
        "prior_shots":prior_shots,"prior_rate":prior_rate,
        "no_same_day_outcome_features":True,"odds_used":False,
        "no_starter_confirmation":True,"model_promoted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True);p.add_argument("--output",required=True);p.add_argument("--manifest",required=True)
    a=p.parse_args();rows,meta=derive(a.archive)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(rows,indent=2));meta["sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
    Path(a.manifest).write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=="__main__":main()
