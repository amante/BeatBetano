"""Audit provenance and completeness of ESPN historical player boxscore samples.

This is postgame collection coverage, not historical pregame injury coverage.
Never represent the sample as a complete league-season dataset.
"""
import argparse,json
from pathlib import Path

def audit(history, sample):
    if not isinstance(history,list) or not history:
        raise ValueError("Historical ledger required")
    requested=sample.get("games_requested")
    rows=sample.get("players")
    missing=sample.get("unavailable_games")
    if not isinstance(requested,int) or requested<1 or not isinstance(rows,list) or not isinstance(missing,list):
        raise ValueError("Malformed player sample")
    ledger={str(g["game_id"]):g for g in history}
    if len(ledger)!=len(history):raise ValueError("Duplicate ledger IDs")
    success={}
    for row in rows:
        gid=str(row["game_id"])
        if gid not in ledger or row.get("team") not in (ledger[gid]["home_team"],ledger[gid]["away_team"]):
            raise ValueError("Unmatched player game/team")
        if row.get("availability_known_pregame") is not False:
            raise ValueError("Postgame evidence falsely marked as pregame")
        success.setdefault(gid,[]).append(row)
    failed=[str(x["game_id"]) for x in missing]
    if len(set(failed))!=len(failed) or set(failed)&set(success):
        raise ValueError("Overlapping or duplicate failures")
    if requested!=len(success)+len(failed):
        raise ValueError("Inconsistent collected game totals")
    if requested>len(history):raise ValueError("More requested than ledger")
    teams_incomplete=[]
    for gid,people in success.items():
        if {p["team"] for p in people}!={ledger[gid]["home_team"],ledger[gid]["away_team"]}:
            teams_incomplete.append(gid)
    observed_minutes=sum(x.get("minutes_played") is not None for x in rows)
    return {"schema_version":1,"source":sample.get("source"),
      "historical_ledger_games":len(history),"sample_games_requested":requested,
      "sample_games_with_player_rows":len(success),
      "sample_games_failed":len(failed),
      "sample_coverage_fraction":round(len(success)/requested,6),
      "sample_two_team_boxscores":len(success)-len(teams_incomplete),
      "games_missing_two_teams":teams_incomplete,
      "athlete_rows":len(rows),"rows_with_recorded_minutes":observed_minutes,
      "sample_only":True,"full_historical_coverage_verified":False,
      "historical_pregame_availability_verified":False,
      "impact_model_training_authorized":False,
      "note":"A boxscore is a postgame outcome. Historical injuries and starting fives must have independently archived pre-tipoff timestamps."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",required=True)
    parser.add_argument("--sample",required=True)
    parser.add_argument("--output",required=True)
    x=parser.parse_args()
    report=audit(json.loads(Path(x.history).read_text()),
                 json.loads(Path(x.sample).read_text()))
    dest=Path(x.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
