"""NFL pregame availability feature engineering, with strict source provenance.

No postgame snap counts from the target match, no retrospectively revealed
player participation, and no synthetic injury labels in real backtests.
Availability inputs are externally sourced game-time status snapshots.
"""
from pathlib import Path
import pandas as pd

POSITIONS = ("QB","OL","EDGE","DT","LB","CB","S")
OUT = {"OUT","IR","PUP","SUSPENDED","INACTIVE"}
NEEDED = {"game_id","team","player_id","position","status","snapshot_utc","kickoff_utc","source"}

def availability_features(reports, allowed_sources=None):
    """Aggregate verified pre-kickoff status by game/team/position.

    Missing records are *unknown*, not equivalent to a fully healthy roster.
    Calling this function does not infer player quality, starter role or
    replacement ability. Those require separately validated snapshots.
    """
    missing = NEEDED - set(reports.columns)
    if missing:
        raise ValueError(f"Missing required pregame availability columns: {sorted(missing)}")
    d = reports.copy()
    d["snapshot_utc"] = pd.to_datetime(d.snapshot_utc, utc=True, errors="raise")
    d["kickoff_utc"] = pd.to_datetime(d.kickoff_utc, utc=True, errors="raise")
    if d[["game_id","team","player_id","position","status","source"]].isna().any().any():
        raise ValueError("Missing player identifiers/status/source")
    if (d.snapshot_utc > d.kickoff_utc).any():
        raise ValueError("Leakage: snapshot created after kickoff")
    if allowed_sources is not None and not d.source.isin(allowed_sources).all():
        raise ValueError("Unapproved availability source")
    d["position"] = d.position.astype(str).str.upper()
    d["status"] = d.status.astype(str).str.upper()
    d = d[d.position.isin(POSITIONS)]
    d = d.sort_values("snapshot_utc").drop_duplicates(
        ["game_id","team","player_id"], keep="last"
    )
    d["is_out"] = d.status.isin(OUT).astype(int)
    wide = d.pivot_table(index=["game_id","team"],columns="position",
                         values="is_out",aggfunc="sum",fill_value=0)
    wide = wide.reindex(columns=list(POSITIONS), fill_value=0)
    wide.columns = [f"out_{p.lower()}" for p in wide.columns]
    return wide.reset_index()

def attach_availability(games, features):
    """Inner-join only fully observed team-pair availability features.

    Neither missing team reports nor missing games get imputed as zeros.
    """
    required = {"game_id","home_team","away_team"}
    if not required.issubset(games.columns):
        raise ValueError("Games must have game_id, home_team, away_team")
    keys = ["game_id","team"]
    home = features.rename(columns={"team":"home_team"})
    away = features.rename(columns={"team":"away_team"})
    valuecols = [x for x in features.columns if x not in keys]
    h = home.rename(columns={c:f"home_{c}" for c in valuecols})
    a = away.rename(columns={c:f"away_{c}" for c in valuecols})
    joined = games.merge(h,on=["game_id","home_team"],how="inner",validate="many_to_one")
    joined = joined.merge(a,on=["game_id","away_team"],how="inner",validate="many_to_one")
    return joined
