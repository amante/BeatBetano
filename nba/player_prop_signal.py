"""Informational NBA player-prop screening; never feeds game probabilities.

The input is an auditable, point-in-time snapshot assembled by source adapters.
This module intentionally fails closed: no tag is emitted without verified
usage rank, position-defense rank, an actual pregame prop line, and complete
season/matchup history at the same line.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

MARKETS = {"points", "rebounds", "assists", "pra"}
MIN_SEASON_GAMES = 10
MIN_MATCHUP_GAMES = 5
MIN_HIT_RATE = 0.90
BOTTOM_FIVE_RANKS = range(26, 31)  # Normalized scale: 1 = best defense, 30 = worst.


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def parse_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def stat_value(row, market):
    keys = {"points": ("points",), "rebounds": ("rebounds",), "assists": ("assists",),
            "pra": ("points", "rebounds", "assists")}[market]
    values = [row.get(key) for key in keys]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
        return None
    return sum(values)


def hit_rate(history, market, line, direction, opponent=None):
    counted = hits = 0
    for row in history:
        if opponent is not None and row.get("opponent") != opponent:
            continue
        value = stat_value(row, market)
        if value is None:
            continue
        # Pushes do not count as either a hit or a miss.
        if value == line:
            continue
        counted += 1
        hits += int(value > line if direction == "over" else value < line)
    return {"hits": hits, "games": counted, "rate": hits / counted if counted else None}


def _evaluate_prop(prop, game, observed_at):
    reasons = []
    tip = parse_time(game.get("tipoff_utc"))
    if tip is None:
        return {"status": "unavailable", "reasons": ["invalid_tipoff"]}
    if (not prop.get("player_id") or not prop.get("player") or not prop.get("team")
            or prop.get("team") not in (game.get("home_team"), game.get("away_team"))
            or not game.get("opponent") or game.get("opponent") not in (game.get("home_team"), game.get("away_team"))
            or game.get("opponent") == prop.get("team")):
        reasons.append("player_team_or_opponent_identity_unverified")
    if prop.get("market") not in MARKETS:
        reasons.append("unsupported_market")
    line = prop.get("line")
    if type(line) not in (int, float) or not math.isfinite(line) or line < 0:
        reasons.append("missing_prop_line")
    if prop.get("direction") not in ("over", "under"):
        reasons.append("missing_prop_direction")
    source_url = str(prop.get("source_url", "")).split("?", 1)[0].rstrip("/")
    if prop.get("provider") != "rotowire" or source_url != "https://www.rotowire.com/betting/nba/player-props.php":
        reasons.append("unverified_prop_source")
    line_time = parse_time(prop.get("line_observed_at_utc"))
    if not line_time or line_time >= tip or line_time > observed_at:
        reasons.append("prop_line_not_observed_pregame")
    usage_time = parse_time(prop.get("usage_observed_at_utc"))
    if (not prop.get("usage_source_url") or not prop.get("usage_verified") is True
            or type(prop.get("usage_pct")) not in (int, float) or not math.isfinite(prop["usage_pct"])
            or prop.get("usage_rank") != 1 or prop.get("team_usage_coverage_complete") is not True
            or not usage_time or usage_time >= tip or usage_time > observed_at):
        reasons.append("top_usage_not_verified")
    defense = prop.get("opponent_defense") if isinstance(prop.get("opponent_defense"), dict) else {}
    defense_time = parse_time(defense.get("observed_at_utc"))
    if (prop.get("position_verified") is not True or not prop.get("position")
            or defense.get("position") != prop.get("position")
            or defense.get("market") != prop.get("market")
            or type(defense.get("rank")) is not int or defense["rank"] not in BOTTOM_FIVE_RANKS
            or not defense.get("source_url") or not defense_time or defense_time >= tip
            or defense_time > observed_at):
        reasons.append("bottom_five_position_defense_not_verified")
    history = prop.get("history") if isinstance(prop.get("history"), list) else []
    season_id = prop.get("season_id")
    valid_history = []
    seen = set()
    for row in history:
        played = parse_time(row.get("tipoff_utc")) if isinstance(row, dict) else None
        gid = str(row.get("game_id", "")) if isinstance(row, dict) else ""
        observed = parse_time(row.get("observed_at_utc")) if isinstance(row, dict) else None
        if (not played or not gid or gid in seen or played >= tip or not observed
                or observed > observed_at or row.get("season_id") != season_id):
            continue
        seen.add(gid)
        valid_history.append(row)
    if prop.get("season_history_complete") is not True:
        reasons.append("season_history_incomplete")
    if prop.get("matchup_history_complete") is not True:
        reasons.append("matchup_history_incomplete")
    season = hit_rate(valid_history, prop.get("market"), line, prop.get("direction")) if prop.get("market") in MARKETS and isinstance(line, (int, float)) else {"hits": 0, "games": 0, "rate": None}
    matchup = hit_rate(valid_history, prop.get("market"), line, prop.get("direction"), game.get("opponent")) if prop.get("market") in MARKETS and isinstance(line, (int, float)) else {"hits": 0, "games": 0, "rate": None}
    if season["games"] < MIN_SEASON_GAMES:
        reasons.append("season_sample_below_minimum")
    if matchup["games"] < MIN_MATCHUP_GAMES:
        reasons.append("matchup_sample_below_minimum")
    if season["rate"] is None or season["rate"] < MIN_HIT_RATE:
        reasons.append("season_hit_rate_below_90_percent")
    if matchup["rate"] is None or matchup["rate"] < MIN_HIT_RATE:
        reasons.append("matchup_hit_rate_below_90_percent")
    return {
        "player_id": str(prop.get("player_id", "")), "player": prop.get("player"),
        "team": prop.get("team"), "opponent": game.get("opponent"),
        "position": prop.get("position"), "usage_pct": prop.get("usage_pct"),
        "market": prop.get("market"), "direction": prop.get("direction"), "line": line,
        "line_provider": prop.get("provider"), "line_source_url": prop.get("source_url"),
        "line_observed_at_utc": prop.get("line_observed_at_utc"),
        "usage_source_url": prop.get("usage_source_url"), "usage_observed_at_utc": prop.get("usage_observed_at_utc"),
        "position_defense_source_url": defense.get("source_url"),
        "position_defense_observed_at_utc": defense.get("observed_at_utc"),
        "opponent_defense_rank": defense.get("rank"),
        "season": season, "matchup": matchup,
        "status": "eligible_for_user_review" if not reasons else "not_eligible",
        "eligible": not reasons,
        "reasons": reasons,
    }


def build(snapshot):
    observed_at = parse_time(snapshot.get("as_of_utc"))
    if observed_at is None or not isinstance(snapshot.get("games"), list):
        raise ValueError("Props snapshot requires as_of_utc and games")
    games = []
    for game in snapshot["games"]:
        tip = parse_time(game.get("tipoff_utc"))
        if not game.get("game_id") or not tip or tip <= observed_at:
            raise ValueError("Prop screening accepts only uniquely identified pregame fixtures")
        props = game.get("props", [])
        if not isinstance(props, list) or any(not isinstance(prop, dict) for prop in props):
            raise ValueError("Each game's props must be a list of prop records")
        evaluated = [_evaluate_prop(prop, game, observed_at) for prop in props]
        games.append({"game_id": str(game["game_id"]), "home_team": game.get("home_team"),
                      "away_team": game.get("away_team"), "tipoff_utc": game["tipoff_utc"],
                      "status": "candidates_available" if any(x["eligible"] for x in evaluated) else "no_eligible_candidate",
                      "props": evaluated})
    report = {"schema_version": 1, "kind": "nba_informational_player_prop_signals_v1",
              "as_of_utc": snapshot["as_of_utc"], "source_snapshot_sha256": snapshot.get("content_sha256"),
              "calibrated": False, "model_probability_input": False, "parlay_generation": False,
              "thresholds": {"minimum_season_hit_rate": MIN_HIT_RATE, "minimum_matchup_hit_rate": MIN_HIT_RATE,
                             "minimum_season_games": MIN_SEASON_GAMES, "minimum_matchup_games": MIN_MATCHUP_GAMES,
                      "bottom_five_position_defense_ranks": [26, 27, 28, 29, 30]},
              "games": games}
    report["content_sha256"] = digest(report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build(json.loads(Path(args.input).read_text()))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"games": len(report["games"]),
                      "eligible_props": sum(prop["eligible"] for game in report["games"] for prop in game["props"]),
                      "model_probability_input": False, "parlay_generation": False}))


if __name__ == "__main__":
    main()
