"""Fill pregame player-history gaps from ESPN athlete gamelogs.

Only completed historical events before each fixture are retained. Rows are
keyed by ESPN athlete ID; the team field is the player's current fixture team,
not a claim that the historical game was played for that team.
"""
import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes"
STAT_ALIASES = {
    "minutes_played": ("MIN", "MINUTES"),
    "points": ("PTS", "POINTS"),
    "rebounds": ("REB", "REBOUNDS"),
    "assists": ("AST", "ASSISTS"),
    "turnovers": ("TO", "TOV", "TURNOVERS"),
}


def _utc(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"\d{1,2}:\d{2}", text):
            minute, second = map(int, text.split(":"))
            return minute + second / 60 if second < 60 else None
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return float(text)
    return None


def _items(value):
    if isinstance(value, dict):
        return list(value.values())
    return value if isinstance(value, list) else []


def _gamelog_events(payload):
    labels = payload.get("labels") or payload.get("displayNames") or []
    indexed = {}
    metadata = {str(row.get("id")): row for row in _items(payload.get("events"))
                if isinstance(row, dict) and row.get("id") is not None}
    roots = []
    for season_type in _items(payload.get("seasonTypes")):
        if not isinstance(season_type, dict):
            continue
        name = str(season_type.get("name") or season_type.get("displayName") or "").casefold()
        if name and "regular" not in name:
            continue
        for category in _items(season_type.get("categories")):
            if isinstance(category, dict):
                roots.extend(_items(category.get("events")))
    if not roots:
        roots = _items(payload.get("events"))
    for row in roots:
        if not isinstance(row, dict):
            continue
        event_id = str(row.get("eventId") or row.get("id") or "")
        if not event_id:
            continue
        meta = metadata.get(event_id, {})
        date = row.get("gameDate") or row.get("date") or meta.get("gameDate") or meta.get("date")
        stats = row.get("stats")
        if not isinstance(stats, list):
            continue
        combined = {**meta, **row}
        indexed[event_id] = {"event_id": event_id, "date": date,
                             "labels": labels, "stats": stats,
                             "processed": combined.get("gameProcessed", combined.get("gameProcessed", True))}
    return list(indexed.values())


def _stat_map(row):
    result = {}
    for index, label in enumerate(row["labels"]):
        if index < len(row["stats"]):
            result[str(label).strip().upper()] = row["stats"][index]
    output = {}
    for key, aliases in STAT_ALIASES.items():
        value = next((result[name] for name in aliases if name in result), None)
        output[key] = _number(value)
    return output


def _target_players(reconciliation):
    for game in reconciliation.get("games", {}).values():
        for team, players in (game.get("teams") or {}).items():
            for player in players if isinstance(players, list) else []:
                claims = player.get("claims", [])
                if any(claim.get("status") in ("out", "questionable", "doubtful")
                       and claim.get("player_id") for claim in claims):
                    yield str(player["player_id"]), str(team), player.get("player")


def enrich(snapshot, reconciliation, history, session=None, observed_at=None, seasons=2):
    client = session or requests.Session()
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    observed = _utc(observed_at)
    if observed is None:
        raise ValueError("Capture time must include a timezone")
    rows = history.get("players", []) if isinstance(history, dict) else []
    if not isinstance(rows, list):
        rows = []
    games = {str(row.get("game_id")): row for row in snapshot.get("predictions", [])}
    existing = {(str(row.get("player_id")), str(row.get("game_id"))) for row in rows}
    claims = sorted(set(_target_players(reconciliation)))
    diagnostics = []
    appended = []
    for player_id, team, player_name in claims:
        target_fixtures = [game for game in games.values()
                           if team in (game.get("home_team"), game.get("away_team"))]
        cutoffs = [_utc(game.get("tipoff_utc")) for game in target_fixtures]
        cutoffs = [value for value in cutoffs if value]
        if not cutoffs:
            continue
        # Current season is represented by regular ESPN event capture. Query only
        # the previous completed seasons to repair small early-season samples.
        target_year = max(value.year + (1 if value.month >= 7 else 0) for value in cutoffs)
        needed = False
        prior = [row for row in rows if str(row.get("player_id")) == player_id
                 and str(row.get("team")) == team and row.get("minutes_played") is not None]
        if len(prior) >= 3 and any(row.get("points") is not None for row in prior):
            continue
        fetched = 0
        for season in range(target_year - 1, target_year - seasons - 1, -1):
            url = f"{BASE}/{player_id}/gamelog"
            try:
                response = client.get(url, params={"season": season}, timeout=20)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Unexpected ESPN gamelog shape")
                season_rows = _gamelog_events(payload)
                kept = 0
                for item in season_rows:
                    event_time = _utc(item.get("date"))
                    if event_time is None or event_time >= min(cutoffs):
                        continue
                    if item.get("processed") is False:
                        continue
                    if (player_id, item["event_id"]) in existing:
                        continue
                    stats = _stat_map(item)
                    if stats["minutes_played"] is None or stats["minutes_played"] <= 0:
                        continue
                    appended.append({
                        "game_id": item["event_id"], "team": team, "player_id": player_id,
                        "player": player_name, "tipoff_utc": event_time.isoformat(),
                        **stats, "did_not_play": False, "starter_reported_postgame": None,
                        "availability_known_pregame": False, "observed_at_utc": observed_at,
                        "source": "ESPN athlete gamelog", "historical_team_scope": "player_id",
                    })
                    existing.add((player_id, item["event_id"]))
                    kept += 1
                fetched += 1
                if kept:
                    needed = True
                # A single prior season with usable appearances is enough to
                # reach the five-appearance window when current-season data exists.
                if kept >= 3:
                    break
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                diagnostics.append({"player_id": player_id, "player": player_name,
                                    "team": team, "season": season,
                                    "status": "unavailable", "error_type": type(exc).__name__})
        if not any(row.get("player_id") == player_id for row in diagnostics):
            diagnostics.append({"player_id": player_id, "player": player_name, "team": team,
                                "seasons_checked": fetched,
                                "status": "enriched" if needed else "no_usable_prior_games"})
    combined = rows + appended
    result = {**history, "players": combined,
              "historical_fallback": {"source": BASE, "captured_at_utc": observed_at,
                  "claims_checked": len(claims), "rows_added": len(appended),
                  "players": diagnostics,
                  "team_scope_note": "Historical rows are matched by exact ESPN athlete ID; team is the current fixture team.",
                  "fit_for_pregame_availability": False}}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "reconciliation", "player-history", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--seasons", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.seasons <= 3:
        raise ValueError("--seasons must be between 1 and 3")
    read = lambda path: json.loads(Path(path).read_text())
    result = enrich(read(args.snapshot), read(args.reconciliation),
                    read(args.player_history), seasons=args.seasons)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({"claims_checked": result["historical_fallback"]["claims_checked"],
                      "rows_added": result["historical_fallback"]["rows_added"],
                      "players": len(result["historical_fallback"]["players"])}))


if __name__ == "__main__":
    main()
