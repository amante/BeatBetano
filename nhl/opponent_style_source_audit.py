"""Bounded NHL Gamecenter play-by-play coverage audit.

Downloads completed regular-season games only. The captured postgame event data
is evidence for future pregame features; it must never be used for the same
game's forecast. Raw responses are retained gzip-compressed with SHA-256 hashes.
"""
import argparse
import gzip
import hashlib
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from nhl.opponent_style_profile import game_profile, build_report as build_style_report

HOST = "https://api-web.nhle.com/v1"
MAX_RESPONSE_BYTES = 25_000_000
EVENT_TYPES = {
    "shot-on-goal", "missed-shot", "blocked-shot", "goal",
    "hit", "giveaway", "takeaway", "faceoff", "penalty",
}
FIELD_ALIASES = {
    "event_id": {"eventId", "id"},
    "event_type": {"typeDescKey", "typeCode"},
    "event_owner_team_id": {"eventOwnerTeamId", "teamId", "eventTeamId"},
    "situation_code": {"situationCode", "homeSkaters", "awaySkaters"},
    "score_state": {"homeScore", "awayScore"},
    "period": {"periodDescriptor"},
    "time": {"timeInPeriod", "timeRemaining"},
    "x_coordinate": {"xCoord", "xCoordOrigin"},
    "y_coordinate": {"yCoord", "yCoordOrigin"},
    "shot_type": {"shotType"},
    "shooter": {"shootingPlayerId", "scoringPlayerId"},
    "goalie": {"goalieInNetId"},
    "rebound": {"rebound", "reboundFromEventId", "isRebound"},
    "on_ice": {"awayOnIce", "homeOnIce", "playersOnIce", "onIce"},
}


def fetch_json(url, timeout=25):
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "BeatBetano-NHL-opponent-style-audit/1.0",
    })
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Official response exceeded size limit")
    return json.loads(raw), raw


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def event_rows(payload):
    rows = payload.get("plays")
    if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
        return rows
    candidates = []
    for value in _walk(payload):
        if isinstance(value, dict) and (
            "eventId" in value or "typeDescKey" in value
        ) and any(key in value for key in ("details", "timeInPeriod", "periodDescriptor")):
            candidates.append(value)
    deduped = {}
    for row in candidates:
        key = row.get("eventId", row.get("id"))
        if key is not None:
            deduped[str(key)] = row
    return list(deduped.values())


def _all_keys(event):
    return {key for row in _walk(event) for key in row}


def _event_type(event):
    value = event.get("typeDescKey", event.get("typeCode", "unknown"))
    return str(value).strip().lower().replace("_", "-")


def _is_shot_event(event):
    kind = _event_type(event)
    return kind in {"shot-on-goal", "missed-shot", "blocked-shot", "goal"} or "shot" in kind


def audit(date_to, lookback_days=7, max_games=20, output_dir="nhl-opponent-style-audit"):
    if not 1 <= lookback_days <= 30:
        raise ValueError("lookback-days must be in 1..30")
    if not 1 <= max_games <= 50:
        raise ValueError("max-games must be in 1..50")
    end = date.fromisoformat(date_to)
    start = end - timedelta(days=lookback_days - 1)
    calendar_sources = []
    fixtures = []
    for offset in range(lookback_days):
        day = start + timedelta(days=offset)
        url = f"{HOST}/score/{day.isoformat()}"
        try:
            payload, raw = fetch_json(url)
            captured_at = datetime.now(timezone.utc).isoformat()
            calendar_sources.append({
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "retrieved_at_utc": captured_at,
            })
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            calendar_sources.append({
                "url": url, "retrieved_at_utc": captured_at,
                "error": f"{type(error).__name__}: {str(error)[:200]}",
            })
            continue
        for game in payload.get("games", []):
            if not isinstance(game, dict):
                continue
            if game.get("gameType") != 2 or game.get("gameState") not in {"OFF", "FINAL"}:
                continue
            gid = game.get("id")
            if type(gid) is not int or gid <= 0:
                continue
            home = game.get("homeTeam", {}).get("abbrev")
            away = game.get("awayTeam", {}).get("abbrev")
            home_id = game.get("homeTeam", {}).get("id")
            away_id = game.get("awayTeam", {}).get("id")
            if not home or not away or type(home_id) is not int or type(away_id) is not int:
                continue
            fixtures.append({
                "game_id": gid, "date": game.get("gameDate", day.isoformat()),
                "start_utc": game.get("startTimeUTC"), "home": home, "away": away,
                "home_team_id": home_id, "away_team_id": away_id,
                "home_goals": game.get("homeTeam", {}).get("score"),
                "away_goals": game.get("awayTeam", {}).get("score"),
            })
    fixtures.sort(key=lambda row: (row["date"], row["start_utc"] or "", row["game_id"]))
    selected = fixtures[-max_games:]
    root = Path(output_dir)
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    games = []
    totals = Counter()
    type_counts = Counter()
    field_counts = Counter()
    event_counts = Counter()
    event_schema_keys = {}
    failures = []
    for fixture in selected:
        url = f"{HOST}/gamecenter/{fixture['game_id']}/play-by-play"
        try:
            payload, raw = fetch_json(url)
            retrieved = datetime.now(timezone.utc).isoformat()
            rows = event_rows(payload)
            if not rows:
                raise ValueError("No recognizable event rows in play-by-play response")
            digest = hashlib.sha256(raw).hexdigest()
            raw_path = raw_dir / f"{fixture['game_id']}.json.gz"
            raw_path.write_bytes(gzip.compress(raw, mtime=0))
            per_game = Counter()
            kinds = Counter()
            for event in rows:
                keys = _all_keys(event)
                kind = _event_type(event)
                kinds[kind] += 1
                event_schema_keys.setdefault(kind, set()).update(keys)
                per_game["events"] += 1
                if _is_shot_event(event):
                    per_game["shot_events"] += 1
                    for field, aliases in FIELD_ALIASES.items():
                        if aliases & keys:
                            per_game["shot_" + field] += 1
                for field, aliases in FIELD_ALIASES.items():
                    if aliases & keys:
                        per_game["any_" + field] += 1
            style_profile = game_profile(fixture, rows)
            record = {
                **fixture, "status": "captured", "url": url,
                "team_style_profile": style_profile,
                "retrieved_at_utc": retrieved, "sha256": digest,
                "raw_file": str(raw_path.relative_to(root)),
                "response_bytes": len(raw), "event_count": len(rows),
                "event_types": dict(sorted(kinds.items())),
                "field_coverage": dict(sorted(per_game.items())),
                "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            }
            games.append(record)
            totals.update(per_game)
            type_counts.update(kinds)
            for field in FIELD_ALIASES:
                if per_game.get("shot_" + field):
                    event_counts[field] += 1
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            failures.append({
                **fixture, "url": url, "retrieved_at_utc": retrieved,
                "status": "fetch_or_schema_error",
                "error": f"{type(error).__name__}: {str(error)[:240]}",
            })
    style_report = build_style_report([row["team_style_profile"] for row in games])
    report = {
        "kind": "nhl_gamecenter_opponent_style_source_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_window": {"from": start.isoformat(), "through": end.isoformat()},
        "sample_limit": max_games,
        "completed_regular_season_games_found": len(fixtures),
        "games_selected": len(selected),
        "games_captured": len(games),
        "games_failed": len(failures),
        "event_count": sum(row["event_count"] for row in games),
        "event_type_counts": dict(sorted(type_counts.items())),
        "event_field_names": {key: sorted(value) for key, value in sorted(event_schema_keys.items())},
        "games_with_shot_fields": dict(sorted(event_counts.items())),
        "field_names_under_review": {key: sorted(value) for key, value in FIELD_ALIASES.items()},
        "calendar_sources": calendar_sources,
        "games": games,
        "team_style_profile": style_report,
        "failures": failures,
        "limitations": [
            "These are postgame observations; use them only as features for later games.",
            "Field presence is an inventory, not a claim that every NHL event is classified correctly.",
            "On-ice matchup attribution requires a verified shifts feed and time join; play-by-play alone is not assumed sufficient.",
            "An absent rebound or on-ice field is reported as unavailable, never imputed.",
            "NHL EDGE public pages are curated outputs; this audit does not scrape or infer undocumented bulk exports.",
        ],
    }
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# NHL opponent-style source audit",
        "",
        f"- Ventana revisada: {start.isoformat()} a {end.isoformat()}",
        f"- Partidos regulares finalizados encontrados: {len(fixtures)}",
        f"- Seleccionados / capturados / fallidos: {len(selected)} / {len(games)} / {len(failures)}",
        f"- Eventos capturados: {report['event_count']}",
        "",
        "## Tipos de evento",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(type_counts.items()))
    lines.extend(["", "### Campos efectivos por tipo de evento", ""])
    for kind, keys in sorted(event_schema_keys.items()):
        if "shot" in kind or kind == "goal":
            lines.append(f"- {kind}: {', '.join(sorted(keys))}")
    lines.extend(["", "## Campos observados en eventos de tiro", ""])
    for field in FIELD_ALIASES:
        lines.append(f"- {field}: presente en {event_counts.get(field, 0)} de {len(games)} partidos capturados")
    lines.extend([
        "", "## Partidos capturados", "",
        "| Fecha | ID | Partido | Eventos | Tiros/eventos tiro |",
        "|---|---:|---|---:|---:|",
    ])
    for row in games:
        lines.append(
            f"| {row['date']} | {row['game_id']} | {row['away']} @ {row['home']} | "
            f"{row['event_count']} | {row['field_coverage'].get('shot_events', 0)} |"
        )
    lines.extend(["", "## Perfil descriptivo de ataque y defensa", ""])
    lines.append("Este perfil es pospartido y no modifica probabilidades.")
    lines.append("")
    lines.append("| Equipo | PJ muestra | Tiros a puerta | Fallados | Bloqueados | Goles | <25 ft / tiros ubicados |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for team, profile in sorted(style_report["teams"].items()):
        attack = profile["attack"]
        lines.append(
            f"| {team} | {attack['games']} | {attack['shots_on_goal']} | {attack['missed_shots']} | "
            f"{attack['blocked_shot_events']} | {attack['goals']} | "
            f"{attack['distance_bins_ft'].get('0-25', 0)} / {attack['located_unblocked_shots']} |"
        )
    lines.extend(["", "## Límites", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(f"- {item}" for item in style_report["limitations"])
    markdown = "\n".join(lines) + "\n"
    (root / "report.md").write_text(markdown, encoding="utf-8")
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
    if summary_path:
        with summary_path.open("a", encoding="utf-8") as summary:
            summary.write(markdown)
    print(markdown)
    print(json.dumps({
        "games_found": len(fixtures), "games_selected": len(selected),
        "games_captured": len(games), "games_failed": len(failures),
        "events": report["event_count"], "output": str(report_path),
    }))
    if not games:
        raise RuntimeError("No play-by-play games were captured; inspect failures in report.json")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date-to", default=(date.today() - timedelta(days=1)).isoformat())
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--max-games", type=int, default=20)
    parser.add_argument("--output-dir", default="nhl-opponent-style-audit")
    args = parser.parse_args()
    audit(args.date_to, args.lookback_days, args.max_games, args.output_dir)


if __name__ == "__main__":
    main()
