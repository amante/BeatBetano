"""Resolve NFL.com player names to GSIS IDs without ambiguous silent matches."""
import re,unicodedata
import pandas as pd

def norm(value):
    value=unicodedata.normalize("NFKD",str(value)).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()

def resolve(evidence,players):
    required={"player_name","team"}
    if not required.issubset(evidence):raise ValueError("Evidence missing name/team")
    if not {"gsis_id","display_name","team"}.issubset(players):
        raise ValueError("Players input requires gsis_id, display_name, team; join verified roster season/team first")
    e=evidence.copy();p=players.copy()
    e["name_key"]=e.player_name.map(norm);p["name_key"]=p.display_name.map(norm)
    counts=p.groupby(["team","name_key"]).gsis_id.nunique().rename("candidate_count").reset_index()
    distinct=p.drop_duplicates(["team","name_key","gsis_id"])
    unique=counts[counts.candidate_count==1][["team","name_key"]]
    unique=unique.merge(distinct[["team","name_key","gsis_id"]],on=["team","name_key"],validate="one_to_one")
    joined=e.merge(unique,on=["team","name_key"],how="left",validate="many_to_one")
    joined["identity_status"]=joined.gsis_id.notna().map({True:"single_name_candidate_requires_review",False:"unresolved"})
    return joined.drop(columns="name_key")
