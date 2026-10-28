"""Sport-neutral, fail-closed historical ingestion and audit protocol.

Stages: raw collection -> canonicalization -> outcome completeness ->
immutable provenance -> point-in-time feature readiness. Never equate
completed-game observations with pregame information or model validation.
"""
import argparse,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

SPORTS=("nba","nfl","nhl","soccer","tennis")
SCHEMA="historical-records-v1"

def canonical(records,sport):
    if sport not in SPORTS:raise ValueError("Unknown sport")
    if not isinstance(records,list) or not records:raise ValueError("Nonempty record list required")
    out=[];seen=set()
    for r in records:
        if not isinstance(r,dict):raise ValueError("Invalid record")
        identity=str(r.get("game_id") or r.get("event_id") or r.get("id") or "")
        if not identity:raise ValueError("Missing event id")
        if identity in seen:raise ValueError("Duplicate event ID: "+identity)
        seen.add(identity)
        when=r.get("start_utc") or r.get("tipoff_utc") or r.get("date")
        if not when:raise ValueError("Missing event date")
        home=r.get("home_team") or r.get("home")
        away=r.get("away_team") or r.get("away")
        if not home or not away:raise ValueError("Missing participants")
        final=r.get("result_final") or {}
        home_score=r.get("home_goals",r.get("hg",r.get("home_score",final.get("home_goals"))))
        away_score=r.get("away_goals",r.get("ag",r.get("away_score",final.get("away_goals"))))
        if home_score is None or away_score is None:raise ValueError("Missing finished scores")
        if float(home_score)<0 or float(away_score)<0:raise ValueError("Negative result")
        out.append({"sport":sport,"event_id":identity,"date_or_start":str(when),
                    "home":str(home),"away":str(away),
                    "home_final":float(home_score),"away_final":float(away_score),
                    "source_kind":"completed_game_postgame_only"})
    return sorted(out,key=lambda x:(x["date_or_start"],x["event_id"]))

def audit(records,sport,expected=None,source_ref=None):
    rows=canonical(records,sport)
    if expected is not None and len(rows)!=expected:raise ValueError(f"Coverage mismatch: {len(rows)}/{expected}")
    if not source_ref:raise ValueError("A traceable source reference is required")
    data=json.dumps(rows,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    seasons=Counter(x["date_or_start"][:4] for x in rows)
    manifest={"schema":SCHEMA,"sport":sport,"count":len(rows),
              "expected_count":expected,"coverage_complete":expected is not None and len(rows)==expected,
              "sha256":hashlib.sha256(data).hexdigest(),"source_ref":source_ref,
              "years":dict(sorted(seasons.items())),"duplicate_count":0,
              "postgame_outcomes_verified":True,
              "point_in_time_pregame_features_verified":False,
              "calibration_completed":False,"official_model_promoted":False}
    return rows,manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sport",choices=SPORTS,required=True)
    p.add_argument("--input",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--expected-count",type=int)
    p.add_argument("--source-ref",required=True)
    args=p.parse_args()
    rows,manifest=audit(json.loads(Path(args.input).read_text()),args.sport,args.expected_count,args.source_ref)
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    (dest/"canonical_history.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    (dest/"audit_manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
