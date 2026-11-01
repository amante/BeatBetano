"""#267: chronology-safe goalie and team features from official NHL boxscores.

The NHL game row is historical outcome evidence, NEVER a feature for that game.
Date batches are frozen before updating history. Starter must be explicit.
"""
import argparse,csv,json,math
from collections import defaultdict,Counter
from datetime import date,timedelta
from pathlib import Path
from nhl.pulso_historical_boxscores_265 import capture
from nhl.pulso_historical_goalie_join_264 import build

def goalie_totals(row):
    stats=row["source_row"]
    against=stats.get("shotsAgainst")
    saves=stats.get("saves")
    if isinstance(saves,str) and "/" in saves:
        # The API can express saves by situation (e.g. 23/25); do not confuse
        # these strings with a verified total saves quantity.
        saves=None
    if isinstance(against,str) and against.isdigit():against=int(against)
    if isinstance(saves,str) and saves.isdigit():saves=int(saves)
    if type(against) is not int or type(saves) is not int or against<0 or not 0<=saves<=against:
        return None
    return saves,against

def produce(labels,records,min_goalie_shots=50,min_team_games=5):
    if len({str(x["game_id"]) for x in labels})!=len(labels):raise ValueError("Duplicate labels")
    lookup={str(x["game_id"]):x for x in labels}
    if len({str(x["game_id"]) for x in records})!=len(records):raise ValueError("Duplicate boxscores")
    for rec in records:
        label=lookup.get(str(rec["game_id"]))
        if label is None or any(rec[k]!=label[k] for k in ("date","home","away")):
            raise ValueError("Historical source fixture mismatch")
    by_day=defaultdict(list)
    for label in labels:by_day[label["date"]].append(label)
    observed={str(r["game_id"]):r for r in records}
    goalie=defaultdict(lambda:[0,0,0])
    team=defaultdict(lambda:[0,0])
    observations=[];blocked=[]
    for day in sorted(by_day):
        date.fromisoformat(day)
        pending=[]
        for label in by_day[day]:
            gid=str(label["game_id"]);rec=observed.get(gid)
            if rec is None:
                blocked.append({"game_id":gid,"reason":"boxscore_missing"});continue
            if not rec.get("verified_starters"):
                blocked.append({"game_id":gid,"reason":"no_explicit_both_starters"});continue
            side_data={};updates=[]
            for side in ("home","away"):
                side_record=rec["teams"][side]
                ids=[x for x in side_record["goalies"] if x["player_id"]==side_record["starter_id"] and x["explicit_starter"] is True]
                if len(ids)!=1:break
                totals=goalie_totals(ids[0])
                if totals is None:break
                player=side_record["starter_id"];name=label[side]
                shots=goalie[player][1];n=team[name][1]
                side_data[side]={"id":player,"prior_shots":shots,"prior_games":goalie[player][2],
                                 "prior_sv":goalie[player][0]/shots if shots else None,
                                 "team_prior_games":n,
                                 "team_prior_strength":team[name][0]/n-0.5 if n else None}
                updates.append((player,name,*totals))
            if len(side_data)!=2:
                blocked.append({"game_id":gid,"reason":"invalid_starter_stats"});continue
            if any(side_data[s]["prior_shots"]<max(1,min_goalie_shots) or side_data[s]["team_prior_games"]<max(1,min_team_games) for s in ("home","away")):
                blocked.append({"game_id":gid,"reason":"insufficient_prior_sample"})
            else:
                feature_date=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
                observations.append({"game_id":gid,"date":day,"home":label["home"],"away":label["away"],
                    "feature_as_of_date":feature_date,"home_goalie_id":side_data["home"]["id"],
                    "away_goalie_id":side_data["away"]["id"],"home_goalie_prior_sv":side_data["home"]["prior_sv"],
                    "away_goalie_prior_sv":side_data["away"]["prior_sv"],
                    "home_team_prior_strength":side_data["home"]["team_prior_strength"],
                    "away_team_prior_strength":side_data["away"]["team_prior_strength"],
                    "source_verified":True})
            pending.append((label,updates))
        # Only update after all same-day features were calculated.
        for label,updates in pending:
            for player,name,saves,shots in updates:
                goalie[player][0]+=saves;goalie[player][1]+=shots;goalie[player][2]+=1
            team[label["home"]][1]+=1;team[label["away"]][1]+=1
            team[label[label["ml_winner"]]][0]+=1
    joined=build(labels,observations)
    return {"kind":"nhl_historical_goalie_features_267","eligible_rows":joined["eligible_rows"],
        "eligible_count":joined["eligible_count"],"blocked_count":len(blocked),
        "blocked_fixtures":blocked,"training_audit":joined["training_audit"],
        "source_game_count":len(records),"odds_used":False,"calibrated":False,"official_predictions":0}

def main():
    p=argparse.ArgumentParser()
    for name in ("labels","cache-dir","out"):p.add_argument("--"+name,required=True)
    p.add_argument("--start",type=int,default=0);p.add_argument("--count",type=int,default=100)
    p.add_argument("--capture",action="store_true")
    args=p.parse_args()
    if not 0<=args.start<2811 or not 1<=args.count<=300:raise ValueError("Invalid capture window")
    with Path(args.labels).open(newline="") as f:labels=list(csv.DictReader(f))
    if len(labels)!=2811:raise ValueError("Expected full label history")
    subset=labels[args.start:args.start+args.count]
    directory=Path(args.cache_dir)
    if args.capture:capture(subset,directory)
    records=[]
    for label in labels:
        path=directory/(str(label["game_id"])+".json")
        if path.exists():records.append(json.loads(path.read_text()))
    report=produce(labels,records)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ("source_game_count","eligible_count","blocked_count")}))
if __name__=="__main__":main()
