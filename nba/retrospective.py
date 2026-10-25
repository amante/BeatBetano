"""Strict point-in-time NBA retrospective: yesterday's results, no lookahead.

A replay is NOT a historically registered pregame forecast; do not relabel it.
"""
import argparse,json,hashlib
from datetime import datetime,timezone,timedelta,date
from pathlib import Path
from auto_history import build
from espn_games import fetch_range
from prospective import generate
from settle_daily import report

def retrospective(target_date,root,cutoff=None):
    target=date.fromisoformat(target_date)
    cutoff=cutoff or f"{target_date}T00:00:00Z"
    stamp=datetime.fromisoformat(cutoff.replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset()!=timedelta(0):
        raise ValueError("Cutoff must be explicit UTC")
    if stamp.date()!=target or stamp.time().hour!=0 or stamp.minute!=0 or stamp.second!=0:
        raise ValueError("Replay cutoff must be target day 00:00 UTC")
    folder=Path(root);folder.mkdir(parents=True,exist_ok=True)
    history_path=folder/"history.json"
    hist_audit=build(history_path,target_date,cutoff,folder/"raw")
    # Use final score ONLY as target label, never as pregame input.
    finals,raw_events,_=fetch_range(target,target)
    eligible=[g for g in finals if datetime.fromisoformat(g["tipoff_utc"].replace("Z","+00:00"))>stamp]
    if not eligible:raise ValueError("No verified completed fixtures after cutoff")
    fixtures=[dict(g,home_points=None,away_points=None) for g in eligible]
    snap=generate(json.loads(history_path.read_text()),fixtures,cutoff)
    metrics=report(snap,eligible)
    metrics["replay_method"]="RETROSPECTIVE_SIMULATION_NOT_ORIGINAL_PREGAME"
    metrics["target_scoreboard_date"]=target_date
    metrics["cutoff_utc"]=cutoff
    metrics["verified_history_count"]=hist_audit["source_count"]
    metrics["source_raw_events"]=raw_events
    metrics["expected_finals"]=len(eligible)
    metrics["source"]="ESPN completed regular season scoreboard"
    metrics["no_odds_features"]=True
    for row in metrics["games"]:
        g=next(g for g in eligible if g["game_id"]==row["game_id"])
        p=next(p for p in snap["predictions"] if p["game_id"]==row["game_id"])
        row.update({"home_team":g["home_team"],"away_team":g["away_team"],
                    "home_points":g["home_points"],"away_points":g["away_points"],
                    "elo_p_home":p["elo_p_home"],
                    "challenger_p_home":p["challenger_p_home"],
                    "hybrid_p_home":p["hybrid_p_home"],
                    "hybrid_route":p["hybrid_route"]})
    return snap,metrics

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True);p.add_argument("--outdir",required=True)
    a=p.parse_args()
    root=Path(a.outdir);snap,res=retrospective(a.date,root)
    (root/"retrospective_snapshot.json").write_text(json.dumps(snap,indent=2))
    (root/"retrospective_report.json").write_text(json.dumps(res,indent=2))
    print(json.dumps(res,indent=2))
if __name__=="__main__":main()
