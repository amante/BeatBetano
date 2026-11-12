"""Build transparent per-player points/rebounds/assists projections for NBA fixtures."""
import argparse
import hashlib
import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def stamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def name_key(value):
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).split())


def _players(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.get("players", []) if isinstance(value.get("players"), list) else []
    return []


def build(snapshot, module_context, player_history, roster_feed):
    snapshot_sha = snapshot.get("content_sha256")
    if not snapshot_sha or snapshot_sha != digest({k: v for k, v in snapshot.items() if k != "content_sha256"}):
        raise ValueError("Snapshot digest mismatch")
    if module_context.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("Module context / snapshot mismatch")
    context_body = {k: v for k, v in module_context.items() if k != "content_sha256"}
    if module_context.get("content_sha256") != digest(context_body):
        raise ValueError("Module context digest mismatch")
    if roster_feed.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("Roster feed / snapshot mismatch")
    observations = player_history.get("players", [])
    if not isinstance(observations, list):
        raise ValueError("Invalid historical player statistics")
    history_by_player = {}
    game_cutoff = stamp(snapshot.get("created_at_utc"))
    for row in observations:
        played_at = stamp(row.get("tipoff_utc"))
        minutes = row.get("minutes_played")
        if (not row.get("player_id") or not played_at or not game_cutoff or played_at >= game_cutoff
                or row.get("did_not_play") or type(minutes) not in (int, float)
                or not math.isfinite(minutes) or minutes <= 0):
            continue
        history_by_player.setdefault((str(row.get("team")), str(row["player_id"])), []).append(row)

    games = {}
    for fixture in snapshot.get("predictions", []):
        gid = str(fixture["game_id"])
        ctx = module_context.get("games", {}).get(gid, {})
        rotation_module = ctx.get("rotation_minutes", {})
        rotation = rotation_module.get("historical_rotation", {}).get("teams", {})
        joint = rotation_module.get("joint_allocation", {}).get("teams", {})
        availability = rotation_module.get("availability_status", {}).get("teams", {})
        lineup_data = ctx.get("starting_lineups", {}).get("data", {}).get("teams", {})
        roster_game = roster_feed.get("games", {}).get(gid, {}).get("teams", {})
        teams = {}
        for team in (fixture["away_team"], fixture["home_team"]):
            roster = roster_game.get(team, {})
            members = _players(roster.get("players", []))
            if not members:
                members = []
            starters = set(name_key(item) for item in lineup_data.get(team, {}).get("starters", []) if item)
            historical = rotation.get(team, {}).get("provisional_rotation", [])
            historical_by_id = {str(p.get("player_id")): p for p in historical if p.get("player_id")}
            historical_by_name = {}
            for p in historical:
                key = name_key(p.get("player"))
                if key:
                    historical_by_name.setdefault(key, []).append(p)
            joint_allocations = joint.get(team, {}).get("allocations")
            if not isinstance(joint_allocations, dict):
                joint_allocations = {}
            status_rows = availability.get(team, {}).get("players", [])
            status_by_id = {str(p.get("player_id")): p for p in status_rows if p.get("player_id")}
            status_by_name = {name_key(p.get("player")): p for p in status_rows if p.get("player")}
            projected = []
            for member in members:
                if not isinstance(member, dict):
                    continue
                name = member.get("player") or member.get("name")
                pid = str(member.get("player_id") or "")
                if not name or not pid:
                    continue
                hist = historical_by_id.get(pid)
                if not hist:
                    matches = historical_by_name.get(name_key(name), [])
                    hist = matches[0] if len(matches) == 1 else None
                status_row = status_by_id.get(pid) or status_by_name.get(name_key(name), {})
                availability_status = status_row.get("status", "unknown")
                player_history_rows = history_by_player.get((team, str(hist.get("player_id"))), []) if hist else []
                player_history_rows = sorted(player_history_rows, key=lambda row: stamp(row["tipoff_utc"]), reverse=True)[:10]
                recent = player_history_rows[:5]
                historical_minutes = hist.get("minutes_projection") if hist else None
                minutes = joint_allocations.get(pid)
                minutes_source = "availability_adjusted_team_allocation"
                if type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes < 0:
                    minutes = historical_minutes
                    minutes_source = "recent_historical_minutes_not_availability_adjusted"
                if type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes <= 0:
                    minutes = None
                    minutes_source = "insufficient_minutes_evidence"
                metrics = {}
                for metric in ("points", "rebounds", "assists"):
                    sample = [row for row in player_history_rows
                              if type(row.get(metric)) in (int, float) and math.isfinite(row[metric])]
                    weighted_minutes = 0.0
                    weighted_stat = 0.0
                    for index, row in enumerate(sample):
                        weight = 0.9 ** index
                        weighted_minutes += float(row["minutes_played"]) * weight
                        weighted_stat += float(row[metric]) * weight
                    enough = len(sample) >= 3 and sum(float(row["minutes_played"]) for row in sample) >= 60
                    metrics[metric + "_projection"] = round((weighted_stat / weighted_minutes) * minutes, 1) if enough and minutes else None
                    metrics[metric + "_sample_games"] = len(sample)
                reason = None
                if availability_status == "out":
                    reason = "reported_out"
                elif len(player_history_rows) < 3 or sum(float(row["minutes_played"]) for row in player_history_rows) < 60:
                    reason = "insufficient_historical_sample"
                elif minutes is None:
                    reason = "insufficient_minutes_evidence"
                projected.append({
                    "player_id": pid,
                    "player": name,
                    "role": "starter_listed_by_provider" if name_key(name) in starters else "roster_member_role_unconfirmed",
                    "availability_status": availability_status,
                    "projection_status": "unavailable" if reason == "reported_out" else "insufficient_data" if reason else "estimated",
                    "projection_reason": reason,
                    "projected_minutes": round(float(minutes), 1) if minutes is not None else None,
                    "minutes_source": minutes_source,
                    "historical_games": len(player_history_rows),
                    **metrics,
                })
            projected.sort(key=lambda p: (p["role"] != "starter_listed_by_provider",
                                         p["projected_minutes"] is None,
                                         -(p["projected_minutes"] or 0), p["player"].casefold()))
            teams[team] = {
                "status": "available" if projected else "roster_unavailable",
                "roster_verified": roster.get("roster_complete") is True,
                "roster_source": roster.get("source_url"),
                "observed_at_utc": roster.get("observed_at_utc"),
                "availability_adjusted_minutes": bool(joint_allocations),
                "players": projected,
                "note": "Historical per-minute production multiplied by projected minutes; this is a statistical estimate, not a sportsbook line. Availability is incorporated only when the verified team allocation is available."
            }
        games[gid] = {"away_team": fixture["away_team"], "home_team": fixture["home_team"], "teams": teams}
    report = {
        "schema_version": 1,
        "kind": "nba_player_stat_projections_v1",
        "snapshot_sha256": snapshot_sha,
        "calibrated": False,
        "probabilities_adjusted": False,
        "method": "recency_weighted_last_10_appearances_per_minute_x_projected_minutes",
        "minimum_sample": {"appearances_per_stat": 3, "observed_minutes_per_stat": 60},
        "games": games,
    }
    report["content_sha256"] = digest(report)
    return report


def main():
    parser = argparse.ArgumentParser()
    for name in ("snapshot", "module-context", "players", "roster", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    report = build(read(args.snapshot), read(args.module_context), read(args.players), read(args.roster))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"games": len(report["games"]),
                      "players": sum(len(team["players"]) for game in report["games"].values() for team in game["teams"].values()),
                      "probabilities_adjusted": False}))


if __name__ == "__main__":
    main()
