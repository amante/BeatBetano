"""Link timestamped NFL inactive snapshots to prior depth-chart candidates.

Only authenticated pregame inactive snapshots qualify. A retrospective
'deactivated' player entry without a historic capture timestamp is NOT eligible.
"""
import argparse,json
from pathlib import Path
import pandas as pd

COLUMNS={"game_id","team","gsis_id","inactive","observed_at_utc","kickoff_utc","source"}
def link_inactives(depth,inactives):
    if not COLUMNS.issubset(inactives.columns):
        raise ValueError(f"Missing inactive fields: {sorted(COLUMNS-set(inactives.columns))}")
    needed={"game_id","team","gsis_id","dt","kickoff_utc","pos_abb","pos_slot","pos_rank"}
    if not needed.issubset(depth.columns):
        raise ValueError(f"Missing depth columns: {sorted(needed-set(depth.columns))}")
    x=inactives.copy()
    if x[list(COLUMNS)].isna().any().any():
        raise ValueError("Incomplete pregame inactive records")
    x["observed_at_utc"]=pd.to_datetime(x.observed_at_utc,utc=True,errors="raise")
    x["kickoff_utc"]=pd.to_datetime(x.kickoff_utc,utc=True,errors="raise")
    if (x.observed_at_utc>=x.kickoff_utc).any():
        raise ValueError("Inactive snapshot must precede kickoff")
    if not x["inactive"].isin([True,False,0,1]).all():
        raise ValueError("Inactive must be a boolean status")
    x=x.sort_values("observed_at_utc").drop_duplicates(["game_id","team","gsis_id"],keep="last")
    d=depth.copy()
    d["dt"]=pd.to_datetime(d.dt,utc=True,errors="raise")
    d["kickoff_utc"]=pd.to_datetime(d.kickoff_utc,utc=True,errors="raise")
    if (d.dt>=d.kickoff_utc).any():
        raise ValueError("Depth snapshot must precede kickoff")
    if d.duplicated(["game_id","team","gsis_id"]).any():
        raise ValueError("Ambiguous player depth candidate")
    joined=d.merge(x[["game_id","team","gsis_id","inactive","observed_at_utc","source"]],
                   on=["game_id","team","gsis_id"],how="left",validate="one_to_one",indicator=True)
    joined["inactive_known"]=joined["_merge"].eq("both")
    joined["confirmed_inactive"]=joined["inactive"].where(joined.inactive_known,pd.NA)
    # Unmatched players remain unknown, not 'active'.
    return joined.drop(columns="_merge")

def audit(depth_file,inactive_file,output):
    d=pd.read_csv(depth_file,low_memory=False)
    x=pd.read_csv(inactive_file,low_memory=False)
    result=link_inactives(d,x)
    o=Path(output);o.mkdir(parents=True,exist_ok=True)
    result.to_csv(o/"linked_pregame_player_status.csv",index=False)
    coverage={"depth_player_rows":len(result),
              "matched_player_rows":int(result.inactive_known.sum()),
              "matched_pct":round(result.inactive_known.mean()*100,2) if len(result) else 0,
              "status":"point_in_time_data_audit_only_not_starter_confirmation"}
    (o/"coverage.json").write_text(json.dumps(coverage,indent=2))
    print(json.dumps(coverage,indent=2))
    return coverage

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--depth",required=True)
    p.add_argument("--inactives",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args();audit(a.depth,a.inactives,a.output)
