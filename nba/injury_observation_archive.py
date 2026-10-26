"""Archive point-in-time ESPN injury observations for future empirical study.

An observation is a dated source assertion, not confirmed participation or
a causal impact coefficient. Do not backfill observations after tipoff.
"""
import argparse,json,hashlib
from datetime import datetime,timezone
from pathlib import Path

def timestamp(value):
    t=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if t.tzinfo is None or t.utcoffset()!=timezone.utc.utcoffset(t):
        raise ValueError("UTC timestamp required")
    return t

def archive(snapshot,sporting,preview=None):
    if not isinstance(snapshot.get("predictions"),list):raise ValueError("Missing games")
    created=timestamp(snapshot["created_at_utc"])
    if (preview or {}).get("snapshot_sha256") not in (None,snapshot["content_sha256"]):
        raise ValueError("Preview references another snapshot")
    sources=(sporting or {}).get("games",{})
    previews=(preview or {}).get("games",{})
    games=[]
    for g in snapshot["predictions"]:
        gid=str(g["game_id"]);tip=timestamp(g["tipoff_utc"])
        if not created<tip:raise ValueError("Post-tipoff snapshot")
        teams={g["home_team"],g["away_team"]}
        items=[];issues=[]
        primary=sources.get(gid,{}).get("supplementary_injury_observations",{})
        if primary:
            observed=primary.get("observed_at_utc")
            try:timely=timestamp(observed)<=created and timestamp(observed)<tip
            except (ValueError,TypeError):timely=False
            if not timely:issues.append("sporting_injury_source_not_point_in_time")
            elif not primary.get("source"):issues.append("sporting_injury_source_missing_url")
            else:
                for i in primary.get("items",[]):
                    if not isinstance(i,dict) or i.get("team") not in teams or not i.get("player"):
                        issues.append("unresolved_player_or_team")
                        continue
                    items.append({"team":i["team"],"player":i["player"],
                      "status":i.get("status"),"detail":i.get("detail"),
                      "source":primary["source"],"observed_at_utc":observed,
                      "officially_verified":False})
        secondary=previews.get(gid,{})
        if secondary:
            observed=secondary.get("observed_at_utc")
            try:timely=timestamp(observed)<=created and timestamp(observed)<tip
            except (ValueError,TypeError):timely=False
            if not timely:issues.append("preview_not_point_in_time")
            elif secondary.get("retrieval_status")=="unavailable":
                issues.append("preview_unavailable")
            else:
                # Existing preview parsing does not provide a reliable team crosswalk.
                # Preserve raw labels only; no promotion into team-specific injuries.
                if secondary.get("injury_observations"):
                    issues.append("preview_player_team_resolution_pending")
        games.append({"game_id":gid,"home_team":g["home_team"],
           "away_team":g["away_team"],"tipoff_utc":g["tipoff_utc"],
           "snapshot_as_of_utc":snapshot["created_at_utc"],"observations":items,
           "issues":sorted(set(issues)),"official_status_verified":False,
           "starting_fives_verified":False})
    return {"schema_version":1,"model":"NBA_POINT_IN_TIME_INJURY_OBSERVATIONS",
      "snapshot_sha256":snapshot["content_sha256"],"games":games,
      "observation_count":sum(len(g["observations"]) for g in games),
      "historical_retroactive_backfill_allowed":False,"impact_training_authorized":False,
      "note":"Archive only observations actually collected before tipoff. ESPN is supplementary. No model impact or lineup confirmation inferred."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--sporting",required=True)
    p.add_argument("--preview")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    load=lambda name:json.loads(Path(name).read_text()) if name and Path(name).is_file() else {}
    report=archive(load(args.snapshot),load(args.sporting),load(args.preview))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2))
    print(json.dumps({"games":len(report["games"]),"observations":report["observation_count"],"authorized":False}))
if __name__=="__main__":main()
