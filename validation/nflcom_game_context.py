"""Assign NFL.com injury rows to verified teams and games via explicit context.

No guessed affiliations from player names. Injury league pages may list
multiple teams; a flat player table alone is insufficient to infer team.
"""
import argparse,json
from pathlib import Path
import pandas as pd

def attach_context(rows,assignments,schedule):
    need={"source_url","captured_at_utc","player_name","position","game_status"}
    if not need.issubset(rows.columns):raise ValueError("Missing parsed injury fields")
    keys=["source_url","player_name","position","game_status"]
    required=set(keys)|{"team","game_id"}
    if not required.issubset(assignments.columns):raise ValueError("Missing verified context fields")
    if assignments.duplicated(keys).any():
        raise ValueError("Ambiguous player-row context; add a unique source-row identifier")
    if not {"game_id","home_team","away_team","kickoff_utc"}.issubset(schedule.columns):
        raise ValueError("Missing schedule fields")
    a=rows.merge(assignments[keys+["team","game_id"]],on=keys,how="left",validate="many_to_one",indicator=True)
    a["context_status"]=a["_merge"].map({"both":"mapped_pending_time_and_identity","left_only":"unresolved"})
    a=a.drop(columns="_merge")
    g=schedule[["game_id","home_team","away_team","kickoff_utc"]]
    if g.game_id.duplicated().any():raise ValueError("Duplicate schedule game_id")
    a=a.merge(g,on="game_id",how="left",validate="many_to_one")
    valid=a.team.eq(a.home_team)|a.team.eq(a.away_team)
    a.loc[a.game_id.notna() & ~valid,"context_status"]="invalid_team_game"
    observed=pd.to_datetime(a.captured_at_utc,utc=True,errors="coerce")
    kickoff=pd.to_datetime(a.kickoff_utc,utc=True,errors="coerce")
    a.loc[a.game_id.notna() & ~(observed<kickoff),"context_status"]="not_pregame"
    a.loc[a.game_id.notna() & valid & (observed<kickoff),"context_status"]="pregame_context_verified_identity_pending"
    return a

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--rows",required=True);ap.add_argument("--assignments",required=True)
    ap.add_argument("--schedule",required=True);ap.add_argument("--output",required=True)
    args=ap.parse_args()
    d=attach_context(pd.read_csv(args.rows),pd.read_csv(args.assignments),pd.read_csv(args.schedule))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    d.to_csv(out/"context_audit.csv",index=False)
    summary=d.context_status.value_counts().to_dict()
    (out/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
