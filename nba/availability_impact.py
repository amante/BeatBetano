"""Point-in-time NBA starter/bench availability feature candidates.

A verified roster report can support a numeric *feature*, NOT a win-probability
adjustment. This module cannot certify or authorize a final prediction.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

def utc(value):
    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("UTC evidence timestamp required")
    return value

def team_features(record, snapshot_time, tip):
    if not isinstance(record, dict):
        return None
    time = record.get("source_observed_at_utc")
    if not time:
        return None
    try:
        observed = utc(time)
    except (ValueError, TypeError):
        return None
    if observed > snapshot_time or observed >= tip:
        return None
    if not (record.get("lineup_verified") is True and
            record.get("rotation_verified") is True and
            record.get("official_injury_report_verified") is True):
        return None
    starters = record.get("confirmed_starters")
    bench = record.get("bench_rotation")
    injuries = record.get("official_injuries")
    if not isinstance(starters, list) or len(starters) != 5 or len(set(starters)) != 5:
        return None
    if not isinstance(bench, list) or not isinstance(injuries, list):
        return None
    minutes = 0.0
    for item in bench:
        if not isinstance(item, dict) or not item.get("player"):
            return None
        amount = item.get("expected_minutes")
        if type(amount) not in (float, int) or not math.isfinite(amount) or not 0 <= amount <= 48:
            return None
        minutes += amount
    if minutes > 240:
        return None
    # Injury observations are not converted into numerical player quality.
    # Counts retain labels only where structured, verified reports exist.
    statuses = {"out": 0, "questionable": 0, "doubtful": 0}
    for item in injuries:
        if not isinstance(item, dict) or not item.get("player"):
            return None
        state = str(item.get("status", "")).lower()
        if state in statuses:
            statuses[state] += 1
    return {"verified_starters": 5, "bench_players": len(bench),
            "expected_bench_minutes": round(minutes, 2),
            "injury_counts": statuses, "observed_at_utc": time}

def build(snapshot, roster):
    if roster.get("snapshot_sha256") != snapshot.get("content_sha256"):
        raise ValueError("Roster evidence belongs to a different snapshot")
    created = utc(snapshot["created_at_utc"])
    recorded = roster.get("games", {})
    output = {}
    for game in snapshot["predictions"]:
        gid = str(game["game_id"])
        tip = utc(game["tipoff_utc"])
        evidence = recorded.get(gid, {})
        home = team_features(evidence.get("home"), created, tip)
        away = team_features(evidence.get("away"), created, tip)
        complete = (home is not None and away is not None and
                    evidence.get("positional_matchups_verified") is True and
                    created < tip)
        output[gid] = {
            "home_team": game["home_team"], "away_team": game["away_team"],
            "home_features": home, "away_features": away,
            "feature_complete": bool(complete),
            "candidate_log_odds_delta": None,
            "availability_impact_calibrated": False,
            "status": "candidate_features_only" if complete else "missing_verified_point_in_time_features"}
    return {"schema_version": 1, "model": "NBA_AVAILABILITY_CANDIDATE_2026_27_1",
            "snapshot_sha256": snapshot["content_sha256"],
            "games": output, "final_probabilities_authorized": False,
            "note": "No coefficients fitted; feature extraction is not evidence of calibrated player impact."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build(json.loads(Path(args.snapshot).read_text()),
                   json.loads(Path(args.roster).read_text()))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({"games":len(report["games"]),
        "complete_features":sum(x["feature_complete"] for x in report["games"].values()),
        "approved_adjustments":0}))

if __name__ == "__main__":
    main()
