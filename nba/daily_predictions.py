"""Generate reproducible odds-free NBA game probabilities for a selected date.

Requires independently ingested historical results and an official fixtures
snapshot. Rejects leaking completed games from the requested prediction date.
This is Elo benchmark output, not the calibrated full NBA official model.
"""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import evaluate

def predict(history,fixtures,target_date):
    cutoff=target_date+"T00:00:00+00:00"
    cutoff_dt=datetime.fromisoformat(cutoff)
    good=[]
    for row in history:
        dt=datetime.fromisoformat(str(row["tipoff_utc"]).replace("Z","+00:00"))
        if dt.tzinfo is None:raise ValueError("History timestamp missing timezone")
        if dt.astimezone(timezone.utc)>=cutoff_dt:
            raise ValueError("Historical game at/after UTC start of target date")
        if row.get("home_points") is None or row.get("away_points") is None:
            raise ValueError("History contains incomplete fixture")
        good.append(row)
    if not good:raise ValueError("No validated historical games available")
    games=[];seen=set()
    for row in fixtures:
        dt=datetime.fromisoformat(str(row["tipoff_utc"]).replace("Z","+00:00"))
        if dt.tzinfo is None:raise ValueError("Fixture timestamp missing timezone")
        if dt.astimezone(timezone.utc).date().isoformat()!=target_date:
            raise ValueError("Fixture outside requested UTC date")
        if row.get("home_points") is not None or row.get("away_points") is not None:
            raise ValueError("Refuse game results in pregame fixtures")
        gid=str(row["game_id"])
        if gid in seen:raise ValueError("Duplicate fixture")
        seen.add(gid)
        games.append(dict(row))
    if not games:raise ValueError("No fixtures to predict")
    # Each fixture is predicted against the same end-of-history ratings.
    predictions=[]
    ordered=sorted(good,key=lambda r:(r["tipoff_utc"],str(r["game_id"])))
    maxseason=max(int(g["season"]) for g in ordered+games)
    minseason=min(int(g["season"]) for g in ordered+games)
    for fixture in games:
        merged=ordered+[fixture]
        result=list(evaluate(merged,season_min=minseason,season_max=maxseason))[-1]
        predictions.append({"game_id":result.game_id,"tipoff_utc":result.date,
            "away_team":result.away,"home_team":result.home,
            "p_away":round(result.p_away,6),"p_home":round(result.p_home,6),
            "dual_sport_filter":result.dual_eligible,
            "model":"nba_elo_benchmark_v0.1",
            "validated_calibration":False,
            "availability_and_lineups_included":False})
    return sorted(predictions,key=lambda r:(r["tipoff_utc"],r["game_id"]))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",required=True)
    parser.add_argument("--fixtures",required=True)
    parser.add_argument("--date",required=True,help="UTC calendar date YYYY-MM-DD")
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    rows=predict(json.loads(Path(a.history).read_text()),
                 json.loads(Path(a.fixtures).read_text()),a.date)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))
