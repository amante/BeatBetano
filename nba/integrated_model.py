"""Single NBA two-layer forecast: statistical baseline + verified sporting adjustment.

Never derive an injury adjustment from a player name or unverified source.
A sport-adjusted probability is emitted ONLY with complete pre-tipoff evidence,
a separately validated impact model, and a traceable log-odds adjustment.
"""
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from full_pregame_gate import REQUIRED

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timezone.utc.utcoffset(d):
        raise ValueError("UTC datetime required")
    return d

def integrate(snapshot,evidence,sporting_data=None):
    original={k:v for k,v in snapshot.items() if k!="content_sha256"}
    sha=hashlib.sha256(json.dumps(original,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if sha!=snapshot.get("content_sha256"):raise ValueError("Tampered statistical snapshot")
    records=evidence.get("games",{})
    supplemental=(sporting_data or {}).get("games",{})
    if not isinstance(records,dict):raise ValueError("Expected games evidence mapping")
    output=[]
    created=utc(snapshot["created_at_utc"])
    for p in snapshot["predictions"]:
        row=records.get(str(p["game_id"]),{})
        tip=utc(p["tipoff_utc"])
        checks={}
        for key in REQUIRED:
            x=row.get(key,{})
            good=isinstance(x,dict) and x.get("verified") is True and bool(x.get("source")) and bool(x.get("observed_at_utc"))
            if good:
                try:good=utc(x["observed_at_utc"])<tip and utc(x["observed_at_utc"])<=created
                except (ValueError,TypeError):good=False
            checks[key]=bool(good)
        impact=row.get("availability_impact",{})
        # Only a registered, externally validated impact estimator may
        # transform baseline probability. No manually guessed deltas.
        validation=impact.get("calibration",{}) if isinstance(impact,dict) else {}
        certified=isinstance(validation,dict) and validation.get("independent_holdout_passed") is True and bool(validation.get("report_ref")) and bool(validation.get("model_version"))
        delta=impact.get("log_odds_delta") if isinstance(impact,dict) else None
        valid_delta=type(delta) in (int,float) and math.isfinite(delta) and abs(delta)<=1.5
        complete=all(checks.values())
        base=p["hybrid_p_home"]
        if not isinstance(base,(int,float)) or not 0<base<1:raise ValueError("Invalid baseline")
        integrated=None
        if complete and certified and valid_delta and created<tip:
            logit=math.log(base/(1-base))
            integrated=1/(1+math.exp(-(logit+delta)))
        status=("statistical_baseline_only" if not complete else
                "awaiting_independent_impact_validation" if not certified or not valid_delta else
                "integrated_candidate")
        output.append({"game_id":p["game_id"],"home_team":p["home_team"],"away_team":p["away_team"],
                       "tipoff_utc":p["tipoff_utc"],
                       "sporting_observations":supplemental.get(str(p["game_id"]),{}),
                       "elo_p_home":p["elo_p_home"],
                       "challenger_p_home":p["challenger_p_home"],
                       "hybrid_p_home":base,"evidence_checks":checks,
                       "all_sporting_steps_verified":complete,
                       "impact_model_independently_validated":certified,
                       "integrated_p_home":integrated,
                       "eligible_for_bet":False,"status":status})
    return {"schema_version":1,"model":"NBA_INTEGRATED_CANDIDATE_2026_27",
            "statistical_snapshot_sha256":snapshot["content_sha256"],
            "predictions":output,"all_games_integrated":all(x["integrated_p_home"] is not None for x in output),
            "no_bookmaker_odds_as_input":True,
            "note":"Single integrated output; null until every pregame step and independently validated impact estimator are available."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--sporting-data")
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    snapshot=json.loads(Path(a.snapshot).read_text())
    evidence=json.loads(Path(a.evidence).read_text()) if a.evidence else {}
    sporting=json.loads(Path(a.sporting_data).read_text()) if a.sporting_data else {}
    result=integrate(snapshot,evidence,sporting)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x") as f:json.dump(result,f,indent=2)
    print(json.dumps({"games":len(result["predictions"]),"integrated":sum(x["integrated_p_home"] is not None for x in result["predictions"])},indent=2))
if __name__=="__main__":main()
