"""Pregame-only NFL starter role and replacement mapping (data contract).

This module never derives depth chart from target-game snaps or injury archives.
All role and replacement records must have independently auditable pre-kickoff
timestamps. Role quality rankings are intentionally not inferred.
"""
import pandas as pd

ROLES={"QB1","LT","LG","C","RG","RT","EDGE1","EDGE2","DT1","DT2",
       "LB1","LB2","CB1","CB2","NICKEL","FS","SS"}
STATUSES={"ACTIVE","OUT","QUESTIONABLE","DOUBTFUL","INACTIVE","IR",
          "PUP","SUSPENDED","UNKNOWN"}
ABSENT={"OUT","INACTIVE","IR","PUP","SUSPENDED"}
REQUIRED={"game_id","team","player_id","role","status","snapshot_utc","kickoff_utc","source"}

def validate_roles(data):
    missing=REQUIRED-set(data.columns)
    if missing:raise ValueError(f"Missing role snapshot fields: {sorted(missing)}")
    d=data.copy()
    if d[list(REQUIRED)].isna().any().any():raise ValueError("Incomplete role snapshots")
    d["snapshot_utc"]=pd.to_datetime(d.snapshot_utc,utc=True,errors="raise")
    d["kickoff_utc"]=pd.to_datetime(d.kickoff_utc,utc=True,errors="raise")
    if (d.snapshot_utc>d.kickoff_utc).any():raise ValueError("Post-kickoff role information prohibited")
    d["role"]=d.role.astype(str).str.upper()
    d["status"]=d.status.astype(str).str.upper()
    if not d.role.isin(ROLES).all():raise ValueError("Unsupported or unverified starter role")
    if not d.status.isin(STATUSES).all():raise ValueError("Unknown roster status")
    # Repeated revisions are fine. Latest pregame observation per player wins.
    d=d.sort_values("snapshot_utc").drop_duplicates(["game_id","team","player_id"],keep="last")
    if d.duplicated(["game_id","team","role"]).any():
        raise ValueError("Conflicting players assigned the same starting role")
    d["confirmed_absent"]=d.status.isin(ABSENT)
    return d

def derive_role_absences(snapshots):
    """Produce only observed role indicators, never interpret missing as healthy."""
    d=validate_roles(snapshots)
    result=d[["game_id","team","role","player_id","confirmed_absent","status","source"]].copy()
    return result

def validate_replacements(replacements,validated_roles):
    """Validate documented candidate replacements, not predicted snaps/quality."""
    required={"game_id","team","absent_player_id","replacement_player_id",
              "role","snapshot_utc","kickoff_utc","source"}
    missing=required-set(replacements.columns)
    if missing:raise ValueError(f"Missing replacement fields: {sorted(missing)}")
    r=replacements.copy()
    if r[list(required)].isna().any().any():raise ValueError("Incomplete replacements")
    r["snapshot_utc"]=pd.to_datetime(r.snapshot_utc,utc=True)
    r["kickoff_utc"]=pd.to_datetime(r.kickoff_utc,utc=True)
    if (r.snapshot_utc>r.kickoff_utc).any():raise ValueError("Post-kickoff replacement forbidden")
    if (r.absent_player_id==r.replacement_player_id).any():raise ValueError("Self replacement")
    roles=validated_roles[validated_roles.confirmed_absent][["game_id","team","role","player_id"]].rename(columns={"player_id":"absent_player_id"})
    m=r.merge(roles,on=["game_id","team","role","absent_player_id"],how="left",indicator=True,validate="many_to_one")
    if not m._merge.eq("both").all():raise ValueError("Replacement lacks confirmed absent starter")
    return m.drop(columns="_merge")
