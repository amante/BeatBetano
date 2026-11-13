"""Prospective NBA injury-status evidence ledger and descriptive calibration.

Only source claims available by the frozen forecast time enter the cohort.
Postgame participation is joined afterward from completed ESPN boxscores.
This module reports observed rates; it does not create prediction weights.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

UNCERTAIN = {"questionable", "doubtful"}


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("UTC timestamp required")
    return parsed.astimezone(timezone.utc)


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def seal(value, field="content_sha256"):
    body = {key: item for key, item in value.items() if key != field}
    if value.get(field) != digest(body):
        raise ValueError("Evidence digest mismatch")


def capture(snapshot, module_context, run_id):
    seal(snapshot)
    seal(module_context)
    if snapshot.get("content_sha256") != module_context.get("snapshot_sha256"):
        raise ValueError("Module context does not match the frozen snapshot")
    frozen_at = stamp(snapshot["created_at_utc"])
    games = []
    excluded_after_freeze = 0
    for fixture in snapshot.get("predictions", []):
        gid = str(fixture["game_id"])
        tip = stamp(fixture["tipoff_utc"])
        if frozen_at >= tip:
            raise ValueError("Cannot capture a post-tipoff prediction")
        evidence = module_context.get("games", {}).get(gid, {}).get(
            "injury_source_reconciliation", {}).get("data", {}).get("teams", {})
        claims = []
        for team in (fixture["home_team"], fixture["away_team"]):
            for player in evidence.get(team, []):
                pid = str(player.get("player_id", ""))
                if not pid:
                    continue
                for claim in player.get("claims", []):
                    status = str(claim.get("status", "")).casefold()
                    if status not in UNCERTAIN:
                        continue
                    try:
                        observed = stamp(claim["observed_at_utc"])
                    except (KeyError, TypeError, ValueError):
                        excluded_after_freeze += 1
                        continue
                    if observed > frozen_at or observed >= tip:
                        excluded_after_freeze += 1
                        continue
                    claims.append({
                        "player_id": pid, "player": player.get("player"),
                        "team": team, "status": status,
                        "source": claim.get("source"),
                        "source_type": claim.get("source_type"),
                        "source_url": claim.get("source_url"),
                        "observed_at_utc": observed.isoformat(),
                        "officially_verified": claim.get("officially_verified") is True,
                        "editorial_claim": claim.get("editorial_claim") is True,
                    })
        games.append({
            "game_id": gid, "home_team": fixture["home_team"],
            "away_team": fixture["away_team"], "tipoff_utc": fixture["tipoff_utc"],
            "prediction_as_of_utc": snapshot["created_at_utc"],
            "claims": claims,
        })
    body = {
        "schema_version": 1, "kind": "nba_injury_status_pregame_capture",
        "capture_run_id": str(run_id), "snapshot_sha256": snapshot["content_sha256"],
        "captured_at_utc": snapshot["created_at_utc"], "games": games,
        "claim_count": sum(len(row["claims"]) for row in games),
        "excluded_after_freeze_count": excluded_after_freeze,
        "postgame_data_used": False, "fit_for_prediction_weights": False,
    }
    body["content_sha256"] = digest(body)
    return body


def settle(capture_doc, boxscores):
    seal(capture_doc)
    if capture_doc.get("kind") != "nba_injury_status_pregame_capture":
        raise ValueError("Expected an NBA pregame injury-status capture")
    players = boxscores.get("players", []) if isinstance(boxscores, dict) else []
    by_event_player = {}
    for row in players:
        key = (str(row.get("game_id")), str(row.get("player_id")), str(row.get("team")))
        if key in by_event_player:
            raise ValueError("Duplicate player row in completed boxscores")
        by_event_player[key] = row
    settled = []
    missing = []
    for game in capture_doc.get("games", []):
        for claim in game.get("claims", []):
            key = (str(game["game_id"]), str(claim["player_id"]), str(claim["team"]))
            row = by_event_player.get(key)
            if row is None:
                missing.append({"game_id": key[0], "player_id": key[1], "source": claim.get("source")})
                continue
            minutes = row.get("minutes_played")
            if type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes < 0:
                actual = False if row.get("did_not_play") is True else None
            else:
                actual = minutes > 0
            settled.append({
                **claim, "game_id": key[0],
                "prediction_as_of_utc": game["prediction_as_of_utc"],
                "tipoff_utc": game["tipoff_utc"],
                "actual_played": actual, "actual_minutes": minutes,
                "boxscore_did_not_play": row.get("did_not_play") is True,
            })
    body = {
        "schema_version": 1, "kind": "nba_injury_status_settlement",
        "capture_run_id": capture_doc["capture_run_id"],
        "snapshot_sha256": capture_doc["snapshot_sha256"],
        "settled_claims": settled, "missing_boxscore_claims": missing,
        "fit_for_prediction_weights": False,
    }
    body["content_sha256"] = digest(body)
    return body


def wilson(successes, total, z=1.959963984540054):
    if total <= 0:
        return None, None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def summarize(settlement_paths):
    latest = {}
    files = sorted(Path(settlement_paths).glob("*.json")) if Path(settlement_paths).is_dir() else []
    for path in files:
        data = json.loads(path.read_text())
        seal(data)
        for row in data.get("settled_claims", []):
            if row.get("actual_played") not in (True, False):
                continue
            key = (str(row["game_id"]), str(row["player_id"]),
                   str(row.get("source")), str(row.get("source_type")))
            observed = stamp(row.get("observed_at_utc") or row["prediction_as_of_utc"])
            old = latest.get(key)
            if old is None or observed > old[0]:
                latest[key] = (observed, row)
            elif observed == old[0] and old[1] is not None and row.get("status") != old[1].get("status"):
                latest[key] = (observed, None)
    groups = {}
    for _, row in latest.values():
        if row is None:
            continue
        key = (str(row.get("source") or "fuente desconocida"),
               str(row.get("status") or "sin estado"),
               str(row.get("source_type") or "tipo desconocido"))
        group = groups.setdefault(key, {"source": key[0], "status": key[1],
                                        "source_type": key[2], "observations": 0,
                                        "played": 0, "did_not_play": 0,
                                        "lead_time_hours": []})
        group["observations"] += 1
        group["played"] += int(row["actual_played"])
        group["did_not_play"] += int(not row["actual_played"])
        lead = (stamp(row["tipoff_utc"]) - stamp(row["prediction_as_of_utc"])).total_seconds() / 3600
        if lead >= 0:
            group["lead_time_hours"].append(lead)
    results = []
    for group in groups.values():
        low, high = wilson(group["played"], group["observations"])
        leads = group.pop("lead_time_hours")
        group["played_rate"] = group["played"] / group["observations"]
        group["played_rate_wilson_95"] = [low, high]
        group["median_lead_time_hours"] = sorted(leads)[len(leads) // 2] if leads else None
        results.append(group)
    results.sort(key=lambda row: (row["source"], row["status"], row["source_type"]))
    return {
        "schema_version": 1, "kind": "nba_injury_status_empirical_summary",
        "groups": results, "unique_settled_source_claims": sum(group["observations"] for group in results),
        "fit_for_prediction_weights": False,
        "note": "Descriptive pregame source-status versus actual participation. Rates are not causal effects or approved probability weights.",
    }

def attach(summary_path, publication_path):
    summary_file = Path(summary_path)
    publication_file = Path(publication_path)
    publication = json.loads(publication_file.read_text())
    if publication.get("kind") != "nba_pulso_research_publication_v1":
        raise ValueError("Unsupported NBA PULSO publication")
    if summary_file.exists():
        summary = json.loads(summary_file.read_text())
        if summary.get("kind") != "nba_injury_status_empirical_summary":
            raise ValueError("Unsupported injury status summary")
        publication["injury_status_calibration"] = summary
    else:
        publication.pop("injury_status_calibration", None)
    publication_file.write_text(json.dumps(publication, indent=2, allow_nan=False) + "\n")
    return publication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture")
    cap.add_argument("--snapshot", required=True)
    cap.add_argument("--module-context", required=True)
    cap.add_argument("--run-id", required=True)
    cap.add_argument("--output", required=True)
    post = commands.add_parser("settle")
    post.add_argument("--capture", required=True)
    post.add_argument("--boxscores", required=True)
    post.add_argument("--output", required=True)
    report = commands.add_parser("summarize")
    report.add_argument("--settlements", required=True)
    report.add_argument("--output", required=True)
    publication = commands.add_parser("attach")
    publication.add_argument("--summary", required=True)
    publication.add_argument("--publication", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    if args.command == "capture":
        result = capture(load(args.snapshot), load(args.module_context), args.run_id)
    elif args.command == "settle":
        result = settle(load(args.capture), load(args.boxscores))
    elif args.command == "summarize":
        result = summarize(args.settlements)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    else:
        result = attach(args.summary, args.publication)
    print(json.dumps({"command": args.command, "games": len(result.get("games", [])),
                      "claims": result.get("claim_count", len(result.get("settled_claims", []))),
                      "groups": len(result.get("groups", []))}))


if __name__ == "__main__":
    main()
