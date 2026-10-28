"""Postgame NHL labels; NEVER pregame features or model validation."""
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

def seconds(clock):
    try:
        minutes,seconds=map(int,clock.split(":"))
        if minutes<0 or seconds<0 or seconds>=60:raise ValueError()
        return minutes*60+seconds
    except (ValueError,AttributeError):
        raise ValueError("Invalid goal clock")

def labels(game):
    gid=str(game["game_id"])
    home=game["home"];away=game["away"]
    final=game["result_final"]
    hg=int(final["home_goals"]);ag=int(final["away_goals"])
    if hg<0 or ag<0:raise ValueError("Negative final score")
    if hg==ag:raise ValueError("NHL completed game cannot finish level")
    raw=game.get("goal_events")
    if not isinstance(raw,list) or not raw:raise ValueError("Missing goal PBP")
    ordered=sorted(raw,key=lambda e:(int(e["period"]),seconds(e["time_in_period"]),int(e["event_id"])))
    seen=set();h=a=0;reg_h=reg_a=0
    h3=a3=False;first=None;first_event=None
    regulation=0;shootout_goals=0
    for event in ordered:
        eid=str(event["event_id"])
        if eid in seen:raise ValueError("Duplicate goal event")
        seen.add(eid)
        period=int(event["period"]);kind=str(event.get("period_type","")).upper()
        if period<1:raise ValueError("Invalid period")
        if kind=="SO":
            shootout_goals+=1
            continue
        if kind not in ("REG","OT"):raise ValueError("Unrecognized period type")
        owner=event.get("owner_team_id")
        # Team IDs are in official boxscore, never infer from scoreboard delta.
        htid=(game.get("boxscore",{}).get("home_team") or {}).get("id")
        atid=(game.get("boxscore",{}).get("away_team") or {}).get("id")
        if htid is None or atid is None or htid==atid:raise ValueError("Missing official team IDs")
        if str(owner)==str(htid):h+=1
        elif str(owner)==str(atid):a+=1
        else:raise ValueError("Goal scored by unknown team")
        if int(event["home_score"])!=h or int(event["away_score"])!=a:
            raise ValueError("PBP goal score sequence inconsistent")
        if kind=="REG":
            if period>3:raise ValueError("Regulation goal after period 3")
            reg_h=h;reg_a=a;regulation+=1
        elif period<4:raise ValueError("OT before period 4")
        if h-a>=3:
            h3=True
            if first is None:first="home";first_event=eid
        if a-h>=3:
            a3=True
            if first is None:first="away";first_event=eid
    # Official NHL final includes shootout-deciding goal, which is not a played goal.
    played_h=h;played_a=a
    is_shootout=shootout_goals>0 or str(game.get("game_info",{}).get("game_state","")).upper()=="SHOOTOUT"
    if (hg,ag)!=(played_h,played_a):
        if not (max(hg-played_h,ag-played_a)==1 and min(hg-played_h,ag-played_a)==0 and
                hg+ag==played_h+played_a+1 and reg_h==reg_a and played_h==played_a):
            raise ValueError("Final score incompatible with goal PBP")
        is_shootout=True
    elif played_h==played_a:raise ValueError("Tied played goals without shootout")
    if is_shootout and played_h!=played_a:raise ValueError("Invalid shootout game")
    if not is_shootout and (hg,ag)!=(played_h,played_a):raise ValueError("Final mismatch")
    if not is_shootout and (hg!=ag) and reg_h==reg_a and played_h==played_a:raise ValueError("OT inconsistency")
    rt="home" if reg_h>reg_a else "away" if reg_a>reg_h else "draw"
    return {"game_id":gid,"date":game["date"],"home":home,"away":away,
      "ml_winner":"home" if hg>ag else "away",
      "rt_home_goals":reg_h,"rt_away_goals":reg_a,"rt_result":rt,
      "overtime_or_shootout":rt=="draw","shootout":is_shootout,
      "home_reached_plus3":h3,"away_reached_plus3":a3,
      "first_to_plus3":first,"first_plus3_event_id":first_event,
      "home_final_goals":hg,"away_final_goals":ag,
      "goal_events_played":regulation+(h+a-reg_h-reg_a),
      "data_class":"POSTGAME_LABELS_NOT_PREGAME_FEATURES"}

def build(root,expected=2811):
    files=sorted(p for p in Path(root).glob("*.json") if p.name!="manifest.json")
    if len(files)!=expected:raise ValueError(f"Expected {expected} individual game records, got {len(files)}")
    output=[];errors=[];ids=set()
    for path in files:
        try:
            game=json.loads(path.read_text())
            record=labels(game)
            if record["game_id"]!=path.stem or record["game_id"] in ids:
                raise ValueError("Incorrect/duplicate game ID")
            ids.add(record["game_id"]);output.append(record)
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            errors.append({"file":path.name,"reason":str(exc)})
    if errors:raise ValueError(f"{len(errors)} goal-label validation failures: {errors[:10]}")
    return sorted(output,key=lambda g:(g["date"],g["game_id"]))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True);p.add_argument("--output",required=True)
    p.add_argument("--expected",type=int,default=2811)
    args=p.parse_args()
    rows=build(args.archive,args.expected)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    target=out/"nhl_postgame_labels.csv"
    with target.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    manifest={"games":len(rows),"sha256":digest,"source":"NHL official gamecenter boxscore and PBP",
      "data_class":"POSTGAME_LABELS_NOT_PREGAME_FEATURES","ml":dict(Counter(x["ml_winner"] for x in rows)),
      "rt":dict(Counter(x["rt_result"] for x in rows)),
      "first_plus3":dict(Counter(str(x["first_to_plus3"]) for x in rows)),
      "shootout_games":sum(x["shootout"] for x in rows),
      "validation":"Strict goal-event sequence and official final-score reconciliation"}
    (out/"labels_manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest))
if __name__=="__main__":main()
