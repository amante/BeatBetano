"""Immutable point-in-time NBA prediction snapshots and result-only settlement.

Input JSON must be verified completed games from historical seasons and 2026-27
season-to-date, plus separate future fixtures. No market information is read.
Snapshots are create-only, UTC stamped, and never updated by settlement.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from model import evaluate
from challenger import predict_challenger
from guardrails import guardrail

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timezone.utc.utcoffset(d):
        raise ValueError("Explicit UTC timestamp required")
    return d

def generate(history,fixtures,created_at):
    created=utc(created_at)
    if not history or not fixtures:raise ValueError("Need completed history and fixtures")
    historical=sorted(history,key=lambda x:(x["tipoff_utc"],str(x["game_id"])))
    seen=set()
    for g in historical:
        if g["home_points"] is None or g["away_points"] is None:raise ValueError("Unfinished history")
        if utc(g["tipoff_utc"])>=created:raise ValueError("Future game in training history")
        if str(g["game_id"]) in seen:raise ValueError("Duplicate historical game")
        seen.add(str(g["game_id"]))
    predictions=[]
    minseason=min(int(x["season"]) for x in historical+fixtures)
    maxseason=max(int(x["season"]) for x in historical+fixtures)
    for game in fixtures:
        gid=str(game["game_id"]);tip=utc(game["tipoff_utc"])
        if gid in seen:raise ValueError("Fixture collides with history")
        if tip<=created:raise ValueError("Fixture already started: not pregame")
        if game.get("home_points") is not None or game.get("away_points") is not None:
            raise ValueError("Results forbidden in fixtures")
        fixture=dict(game,home_points=None,away_points=None)
        rows=historical+[fixture]
        base=list(evaluate(rows,season_min=minseason,season_max=maxseason))[-1]
        challenger=predict_challenger(rows)[-1]
        guarded,route=guardrail(base.p_home,challenger["p_home"],
                               challenger["n_home"],challenger["n_away"])
        predictions.append({"game_id":gid,"tipoff_utc":game["tipoff_utc"],
             "home_team":game["home_team"],"away_team":game["away_team"],
             "elo_p_home":base.p_home,"challenger_p_home":challenger["p_home"],
             "hybrid_p_home":guarded,"hybrid_route":route,
             "dual_challenger":abs(2*challenger["p_home"]-1)<=0.06+1e-12,
             "eligible_for_bet":False,"status":"unvalidated_candidate"})
        seen.add(gid)
    snapshot={"schema_version":1,"created_at_utc":created.isoformat(),
              "predictions":sorted(predictions,key=lambda x:x["game_id"]),
              "source":"user_supplied_verified_inputs",
              "point_in_time_lineups_verified":False,
              "calibrated":False}
    encoded=json.dumps(snapshot,sort_keys=True,separators=(",",":")).encode()
    snapshot["content_sha256"]=hashlib.sha256(encoded).hexdigest()
    return snapshot

def settle(snapshot,results):
    valid={str(g["game_id"]):g for g in results}
    if len(valid)!=len(results):raise ValueError("Duplicate results")
    details=[]
    for p in snapshot["predictions"]:
        g=valid.get(p["game_id"])
        if not g:continue
        if {g["home_team"],g["away_team"]}!={p["home_team"],p["away_team"]}:
            raise ValueError("Team mismatch in official result")
        if g["home_team"]!=p["home_team"]:raise ValueError("Venue mismatch")
        if g["home_points"] is None or g["away_points"] is None:continue
        if utc(g["tipoff_utc"])!=utc(p["tipoff_utc"]):raise ValueError("Tipoff mismatch")
        if utc(snapshot["created_at_utc"])>=utc(g["tipoff_utc"]):raise ValueError("Post-start snapshot")
        y=int(int(g["home_points"])>int(g["away_points"]))
        details.append({"game_id":p["game_id"],"outcome_home":y,
            **{name+"_brier":(p[name+"_p_home"]-y)**2 for name in ("elo","challenger","hybrid")}})
    n=len(details)
    return {"snapshot_sha256":snapshot["content_sha256"],"settled_games":n,
        "total_predictions":len(snapshot["predictions"]),
        "brier":{name:(sum(x[name+"_brier"] for x in details)/n if n else None)
                 for name in ("elo","challenger","hybrid")},
        "games":details}

def main():
    p=argparse.ArgumentParser();p.add_argument("--history");p.add_argument("--fixtures")
    p.add_argument("--timestamp");p.add_argument("--snapshot");p.add_argument("--results")
    p.add_argument("--report");a=p.parse_args()
    if a.results:
        if not a.snapshot or not a.report:raise ValueError("Require snapshot and report")
        out=settle(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.results).read_text()))
        Path(a.report).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));return
    if not all((a.history,a.fixtures,a.timestamp,a.snapshot)):raise ValueError("Required history fixtures timestamp snapshot")
    path=Path(a.snapshot)
    if path.exists():raise FileExistsError("Snapshot is immutable: refusing overwrite")
    result=generate(json.loads(Path(a.history).read_text()),
                    json.loads(Path(a.fixtures).read_text()),a.timestamp)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
