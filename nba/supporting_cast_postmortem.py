"""Slate-wide NBA supporting-cast postgame measurements.

Bench creation, shooting efficiency and defensive event proxies are descriptive
box-score observations. They do not infer causal impact or change model weights.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify(document):
    expected = document.get("content_sha256") if isinstance(document, dict) else None
    body = {key: value for key, value in document.items() if key != "content_sha256"} if isinstance(document, dict) else {}
    if not isinstance(expected, str) or digest(body) != expected:
        raise ValueError("Frozen pregame document digest mismatch")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sum_known(rows, key):
    values = [row.get(key) for row in rows]
    known = [value for value in values if _number(value)]
    return {
        "value": sum(known),
        "known_player_rows": len(known),
        "total_player_rows": len(rows),
        "complete": bool(rows) and len(known) == len(rows),
    }


def _rate(numerator, denominator):
    if not _number(numerator) or not _number(denominator) or denominator <= 0:
        return None
    return numerator / denominator


def _allocation(context_game, team):
    value = ((context_game.get("rotation_minutes") or {}).get("joint_allocation") or {})
    team_data = (value.get("teams") or {}).get(team, {})
    allocations = team_data.get("allocations")
    if not isinstance(allocations, dict):
        return {"status": team_data.get("status") or "unavailable", "minutes": {}}
    cleaned = {str(pid): minutes for pid, minutes in allocations.items() if _number(minutes)}
    if any(minutes < 0 or minutes > 48 for minutes in cleaned.values()):
        raise ValueError("Invalid projected NBA regulation minutes")
    return {"status": team_data.get("status") or "available", "minutes": cleaned}


def _team_report(team, rows, context_game):
    played = [row for row in rows if row.get("did_not_play") is not True]
    bench = [row for row in played if row.get("starter_reported_postgame") is False]
    starters = [row for row in rows if row.get("starter_reported_postgame") is True]
    unclassified = [row for row in rows if row.get("starter_reported_postgame") is None]
    minutes = _sum_known(bench, "minutes_played")
    stats = {key: _sum_known(bench, key) for key in (
        "points", "rebounds", "assists", "turnovers", "steals", "blocks",
        "offensive_rebounds", "defensive_rebounds", "field_goals_made",
        "field_goals_attempted", "three_points_made", "free_throws_attempted",
    )}
    fgm, fga = stats["field_goals_made"], stats["field_goals_attempted"]
    three_made = stats["three_points_made"]
    points = stats["points"]
    fta = stats["free_throws_attempted"]
    shooting_complete = all(item["complete"] for item in (fgm, fga, three_made, points, fta))
    efg = ((fgm["value"] + 0.5 * three_made["value"]) / fga["value"]
           if shooting_complete and fga["value"] > 0 else None)
    ts_denominator = 2 * (fga["value"] + 0.44 * fta["value"]) if shooting_complete else None
    ts = _rate(points["value"], ts_denominator)
    defensive_events = stats["steals"]["value"] + stats["blocks"]["value"]
    defensive_rate = _rate(defensive_events * 36, minutes["value"])
    allocation = _allocation(context_game, team)
    projected = allocation["minutes"]
    by_id = {str(row.get("player_id")): row for row in rows if row.get("player_id")}
    minute_comparisons = []
    for player_id, projected_minutes in sorted(projected.items()):
        actual = by_id.get(player_id)
        actual_minutes = None
        if actual is not None and actual.get("did_not_play") is True:
            actual_minutes = 0.0
        elif actual is not None and _number(actual.get("minutes_played")):
            actual_minutes = float(actual["minutes_played"])
        minute_comparisons.append({
            "player_id": player_id,
            "player": actual.get("player") if actual else None,
            "projected_minutes": projected_minutes,
            "actual_minutes": actual_minutes,
            "actual_starter": actual.get("starter_reported_postgame") if actual else None,
            "actual_bench_player": actual is not None and actual.get("starter_reported_postgame") is False,
            "actual_minus_projected_minutes": round(actual_minutes - projected_minutes, 3) if actual_minutes is not None else None,
            "comparison_status": "observed" if actual_minutes is not None else "player_missing_from_boxscore",
        })
    top_bench = sorted(bench, key=lambda row: (
        -(row.get("minutes_played") or 0), -(row.get("points") or 0), str(row.get("player_id", ""))))
    return {
        "team": team,
        "boxscore_players": len(rows),
        "starters_observed": len(starters),
        "bench_players_observed": len(bench),
        "unclassified_player_rows": len(unclassified),
        "did_not_play_rows": sum(row.get("did_not_play") is True for row in rows),
        "bench_minutes": minutes,
        "bench_production": stats,
        "bench_creation": {
            "assists": stats["assists"],
            "turnovers": stats["turnovers"],
            "assist_to_turnover_ratio": _rate(stats["assists"]["value"], stats["turnovers"]["value"]),
        },
        "bench_efficiency": {
            "effective_field_goal_pct": efg,
            "true_shooting_pct": ts,
            "shooting_fields_complete_for_all_bench_rows": shooting_complete,
            "field_goal_attempts": fga,
            "free_throw_attempts": fta,
        },
        "bench_defense_proxy": {
            "steals": stats["steals"],
            "blocks": stats["blocks"],
            "steals_plus_blocks_per_36_bench_minutes": defensive_rate,
            "interpretation": "Box-score event proxy; not defensive rating or causal defensive impact.",
        },
        "pregame_rotation_status": allocation["status"],
        "projected_to_actual_minutes": minute_comparisons,
        "bench_player_lines": [{
            "player_id": row.get("player_id"),
            "player": row.get("player"),
            "minutes": row.get("minutes_played"),
            "points": row.get("points"),
            "rebounds": row.get("rebounds"),
            "assists": row.get("assists"),
            "turnovers": row.get("turnovers"),
            "steals": row.get("steals"),
            "blocks": row.get("blocks"),
            "field_goals_made": row.get("field_goals_made"),
            "field_goals_attempted": row.get("field_goals_attempted"),
            "three_points_made": row.get("three_points_made"),
            "free_throws_attempted": row.get("free_throws_attempted"),
        } for row in top_bench],
    }


def build(snapshot, module_context, settled, boxscores):
    verify(snapshot)
    verify(module_context)
    snapshot_sha = snapshot["content_sha256"]
    if module_context.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("Pregame module context does not match frozen snapshot")
    if set(module_context.get("games", {})) != {str(row["game_id"]) for row in snapshot.get("predictions", [])}:
        raise ValueError("Pregame context must cover the frozen slate")
    settled_ids = {str(row.get("game_id")) for row in settled.get("games", [])}
    rows = boxscores.get("players", [])
    if not isinstance(rows, list):
        raise ValueError("Player boxscore artifact must include a players list")
    by_game_team = {}
    seen = set()
    for row in rows:
        game_id, team, player_id = str(row.get("game_id", "")), row.get("team"), str(row.get("player_id", ""))
        if not game_id or not team or not player_id:
            continue
        key = (game_id, team, player_id)
        if key in seen:
            raise ValueError("Duplicate player-game boxscore identity")
        seen.add(key)
        by_game_team.setdefault((game_id, team), []).append(row)
    fixtures = {str(row["game_id"]): row for row in snapshot.get("predictions", [])}
    games = []
    for game_id in sorted(set(fixtures) & settled_ids):
        fixture = fixtures[game_id]
        context_game = module_context.get("games", {}).get(game_id, {})
        teams = {}
        for team in (fixture["home_team"], fixture["away_team"]):
            team_rows = by_game_team.get((game_id, team), [])
            teams[team] = _team_report(team, team_rows, context_game)
        games.append({
            "game_id": game_id,
            "home_team": fixture["home_team"],
            "away_team": fixture["away_team"],
            "tipoff_utc": fixture["tipoff_utc"],
            "teams": teams,
            "boxscore_available": all(teams[team]["boxscore_players"] > 0 for team in teams),
        })
    unavailable = {str(row.get("game_id")) for row in boxscores.get("unavailable_games", [])}
    return {
        "schema_version": 1,
        "kind": "nba_supporting_cast_postmortem_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": snapshot_sha,
        "settled_games": len(games),
        "games_with_both_boxscores": sum(row["boxscore_available"] for row in games),
        "player_boxscore_unavailable_games": sorted(unavailable),
        "games": games,
        "model_probabilities_modified": False,
        "causal_player_impact_claimed": False,
        "limitations": [
            "Bench means a player explicitly marked as a non-starter in the postgame boxscore.",
            "Missing starter flags remain unclassified; they are not silently counted as bench.",
            "Shooting efficiency is available only when all required box-score fields are present.",
            "Steals and blocks are descriptive defensive event proxies, not defensive efficiency.",
            "Pregame rotation minutes are conditional projections and actual minutes also reflect game flow and coaching.",
            "No module coefficients or forecast probabilities are changed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "module-context", "settled", "boxscores", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    report = build(load(args.snapshot), load(args.module_context), load(args.settled), load(args.boxscores))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({
        "settled_games": report["settled_games"],
        "games_with_both_boxscores": report["games_with_both_boxscores"],
        "model_probabilities_modified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
