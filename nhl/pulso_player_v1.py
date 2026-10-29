"""PULSO PLAYER NHL v1 — strictly pregame player projections.

This research engine accepts independently sourced *historical player game logs*
with known schedules. A target fixture must provide expected players and expected
context; it never uses outcomes from the game it forecasts. No market odds.
"""
import argparse,csv,json,math
from collections import defaultdict
from datetime import date
from pathlib import Path

FIELDS=("game_id","date","player_id","team","opponent","home","rest_days","toi_minutes","shots_on_goal","goals")
def load_csv(path):
    with Path(path).open(newline="",encoding="utf-8") as file:
        rows=list(csv.DictReader(file))
    return validate(rows)

def validate(rows):
    seen=set();out=[]
    for r in rows:
        if any(r.get(k) in (None,"") for k in FIELDS):
            raise ValueError("Missing required player game log fields")
        key=(str(r["game_id"]),str(r["player_id"]))
        if key in seen:raise ValueError("Duplicate player game")
        seen.add(key)
        try:
            day=date.fromisoformat(r["date"])
            home={"true":True,"false":False,"1":True,"0":False}[str(r["home"]).lower()]
            rest=int(r["rest_days"]);toi=float(r["toi_minutes"])
            sog=int(r["shots_on_goal"]);goals=int(r["goals"])
        except (ValueError,KeyError) as e:raise ValueError("Invalid player game values") from e
        if rest<0 or toi<0 or toi>70 or sog<0 or goals<0 or goals>sog:
            raise ValueError(f"Invalid player statistics player={r['player_id']} game={r['game_id']} date={r['date']} toi={toi} sog={sog} goals={goals} rest={rest}")
        out.append({**r,"date":day.isoformat(),"home":home,
                    "rest_days":rest,"toi_minutes":toi,
                    "shots_on_goal":sog,"goals":goals})
    return sorted(out,key=lambda r:(r["date"],str(r["game_id"]),str(r["player_id"])))

def context_weight(row,target):
    # Soft matching: avoid tiny exact-match samples.
    rest_distance=abs(min(row["rest_days"],5)-min(target["rest_days"],5))
    weight=math.exp(-.32*rest_distance)
    if row["home"]!=target["home"]:weight*=.78
    if row["opponent"]==target["opponent"]:weight*=1.12
    return weight

def forecast(history,target,cutoff,minimum=3):
    """cutoff is the target game's pregame date; only dates STRICTLY before it."""
    day=date.fromisoformat(cutoff)
    if not target.get("player_id") or not target.get("team") or not target.get("opponent"):
        raise ValueError("Missing prediction identity")
    if not isinstance(target.get("home"),bool) or not isinstance(target.get("rest_days"),int) or target["rest_days"]<0:
        raise ValueError("Invalid known pregame context")
    prior=[r for r in history if date.fromisoformat(r["date"])<day and r["team"]==target["team"]]
    own=[r for r in prior if r["player_id"]==str(target["player_id"])]
    if len(own)<minimum:
        return {"player_id":str(target["player_id"]),"date":cutoff,"status":"insufficient_player_history",
                "games":len(own),"projection":None,"odds_used":False}
    # Prior is the player's own unconditional average; contextual deviations
    # are shrunk towards it with 12 pseudo-games.
    base={k:sum(r[k] for r in own)/len(own) for k in ("toi_minutes","shots_on_goal","goals")}
    weights=[]
    for r in own:
        age=(day-date.fromisoformat(r["date"])).days
        weights.append(context_weight(r,target)*math.exp(-math.log(2)*age/150.))
    total=sum(weights)
    projected={}
    for k in base:
        conditional=sum(w*r[k] for w,r in zip(weights,own))/total
        strength=total/(total+12.)
        projected[k]=round(max(0.,base[k]+strength*(conditional-base[k])),4)
    return {"player_id":str(target["player_id"]),"date":cutoff,"status":"research_projection",
            "games":len(own),"effective_sample":round(total,3),
            "projection":projected,"unconditional_average":{k:round(v,4) for k,v in base.items()},
            "method":"player historical contextual similarity, decayed and shrunk",
            "odds_used":False,"validated":False}

def replay(history,start_date="2025-10-01",minimum=3):
    """Expanding chronological player-game audit; no same-day targets in training."""
    results=[]
    for row in history:
        if row["date"]<start_date:continue
        target={k:row[k] for k in ("player_id","team","opponent","home","rest_days")}
        p=forecast(history,target,row["date"],minimum)
        if p["projection"] is None:continue
        results.append({"game_id":row["game_id"],"date":row["date"],
                        "player_id":row["player_id"],"projection":p["projection"],
                        "baseline":p["unconditional_average"],
                        "actual":{k:row[k] for k in p["projection"]}})
    summary={}
    for metric in ("toi_minutes","shots_on_goal","goals"):
        n=len(results)
        summary[metric]={"n":n,
            "baseline_mae":round(sum(abs(x["baseline"][metric]-x["actual"][metric]) for x in results)/n,6) if n else None,
            "contextual_mae":round(sum(abs(x["projection"][metric]-x["actual"][metric]) for x in results)/n,6) if n else None}
    return {"status":"research_only","observations":len(results),"scores":summary,
            "not_independent_validation":True,"pre_game_only":True,"odds_used":False,
            "observations_detail":results}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--logs",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--start",default="2025-10-01")
    a=p.parse_args()
    result=replay(load_csv(a.logs),a.start)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({"observations":result["observations"],"scores":result["scores"]},indent=2))

if __name__=="__main__":main()
