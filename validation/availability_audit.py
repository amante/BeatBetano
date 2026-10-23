"""Point-in-time availability audit; no inference of injury effects.
Run against independently obtained pre-kickoff game and report snapshots.
"""
import argparse
import json
from pathlib import Path
import pandas as pd
from nfl_availability import availability_features, attach_availability

def audit(games_path,reports_path,output):
    games=pd.read_csv(games_path,low_memory=False)
    reports=pd.read_csv(reports_path,low_memory=False)
    required={"game_id","season","home_team","away_team"}
    if not required.issubset(games):
        raise ValueError(f"Missing game columns: {required-set(games)}")
    if games.game_id.duplicated().any():raise ValueError("Duplicate game_id in schedule")
    features=availability_features(reports)
    matched=attach_availability(games,features)
    if matched.game_id.duplicated().any():raise ValueError("Nonunique paired game")
    by_season=games.groupby("season").size().rename("scheduled_games").to_frame()
    covered=matched.groupby("season").size().rename("games_both_teams_reported")
    by_season=by_season.join(covered).fillna(0)
    by_season["coverage_pct"]=(100*by_season.games_both_teams_reported/by_season.scheduled_games).round(2)
    o=Path(output);o.mkdir(parents=True,exist_ok=True)
    by_season.to_csv(o/"coverage_by_season.csv")
    matched.to_csv(o/"paired_availability.csv",index=False)
    summary={"scheduled_games":int(len(games)),"matched_games":int(len(matched)),
             "coverage_pct":round(100*len(matched)/len(games),2) if len(games) else 0,
             "status":"coverage_audit_only_no_predictive_validation"}
    (o/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--reports",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();audit(a.games,a.reports,a.output)
