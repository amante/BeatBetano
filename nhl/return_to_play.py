"""Point-in-time NHL return-to-play minutes evidence and guarded adjustment.

Uses dated NHL.com lineup injury reports plus official NHL player game logs.
A missing lineup appearance never establishes an injury. The adjustment is a
league-pooled, duration-band minutes ramp, not an injury diagnosis or medical claim.
"""
import argparse
import gzip
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
MIN_RETURNING_PLAYERS = 20
SHRINK_PRIOR_EPISODES = 20
MINUTES_FLOOR = 0.70


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def _day(start_utc):
    return _utc(start_utc).astimezone(EASTERN).date()


def _band(days):
    if days <= 3:
        return "1-3"
    if days <= 7:
        return "4-7"
    if days <= 14:
        return "8-14"
    return "15+"


def _ids(values):
    result = {}
    for item in values or []:
        if not isinstance(item, dict):
            continue
        pid = item.get("player_id")
        if type(pid) is int and pid > 0 and item.get("identity_resolved") is True:
            result[pid] = str(item.get("name") or pid)
    return result


def _projected(side):
    projection = side.get("projected") or {}
    players = []
    for group in ("forwards", "defense"):
        for line in projection.get(group) or []:
            players.extend(line or [])
    return _ids(players)


def _snapshots(history_dir, current_report_path, as_of_utc):
    as_of = _utc(as_of_utc)
    paths = set(Path(history_dir).glob("run-*.json"))
    paths.add(Path(current_report_path))
    by_game_team = {}
    for path in sorted(paths):
        try:
            report = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if report.get("kind") != "nhl_pregame_player_evidence_v1":
            continue
        for game in report.get("games", []):
            try:
                game_day = _day(game["start_utc"])
                captured = _utc(game["feature_as_of_utc"])
                start = _utc(game["start_utc"])
            except (KeyError, TypeError, ValueError):
                continue
            if captured >= start or captured > as_of:
                continue
            source = game.get("editorial_source") or {}
            if not str(source.get("url", "")).startswith("https://www.nhl.com/news/nhl-lineup-projections"):
                continue
            for team, side in (game.get("teams") or {}).items():
                key = (str(game.get("game_id")), team)
                row = {
                    "game_id": str(game.get("game_id")),
                    "team": team,
                    "game_day": game_day,
                    "start_utc": game["start_utc"],
                    "captured": captured,
                    "injured": _ids((side.get("projected") or {}).get("injuries")),
                    "active": _projected(side),
                    "source": {"url": source.get("url"), "sha256": source.get("sha256"),
                               "retrieved_at_utc": captured.isoformat()},
                }
                previous = by_game_team.get(key)
                if previous is None or row["captured"] > previous["captured"]:
                    by_game_team[key] = row
    teams = {}
    for row in by_game_team.values():
        teams.setdefault(row["team"], []).append(row)
    for rows in teams.values():
        rows.sort(key=lambda row: (row["game_day"], row["captured"], row["game_id"]))
    return teams


def _episodes(team_snapshots):
    completed = []
    open_by_player = {}
    for snapshot in team_snapshots:
        injured = snapshot["injured"]
        active = snapshot["active"]
        for pid, name in injured.items():
            if pid in active:
                continue
            episode = open_by_player.get(pid)
            if episode is None:
                open_by_player[pid] = {
                    "player_id": pid, "name": name, "team": snapshot["team"],
                    "injury_report_day": snapshot["game_day"],
                    "last_report_day": snapshot["game_day"],
                    "injury_game_id": snapshot["game_id"],
                    "injury_source": snapshot["source"],
                }
            else:
                episode["last_report_day"] = snapshot["game_day"]
                episode["name"] = name or episode["name"]
        conflicts = set(injured) & set(active)
        for pid, name in active.items():
            # A contradictory snapshot cannot close an injury episode.
            if pid in conflicts:
                continue
            episode = open_by_player.pop(pid, None)
            if episode is not None and snapshot["game_day"] >= episode["injury_report_day"]:
                completed.append({**episode, "projected_return_day": snapshot["game_day"],
                                  "projected_return_game_id": snapshot["game_id"],
                                  "projected_return_source": snapshot["source"],
                                  "name": name or episode["name"]})
    return completed, open_by_player


def _toi(value):
    if not isinstance(value, str) or ":" not in value:
        return None
    minutes, seconds = value.split(":", 1)
    if not minutes.isdigit() or not seconds.isdigit() or int(seconds) >= 60:
        return None
    return int(minutes) + int(seconds) / 60.0


def _player_rows(player_id, team, player_sources, raw_logs, game_day, game_start):
    key = str(player_id)
    source_record = (player_sources.get("players") or {}).get(key)
    payload = raw_logs.get(key)
    if not isinstance(source_record, dict) or not isinstance(payload, dict):
        return [], None
    source = source_record.get("source") or {}
    url = source.get("url", "")
    expected = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/"
    if not url.startswith(expected):
        return [], None
    try:
        if _utc(source.get("retrieved_at")) >= _utc(game_start):
            return [], None
    except (TypeError, ValueError):
        return [], None
    rows = []
    for row in payload.get("gameLog", []):
        try:
            played_day = date.fromisoformat(row["gameDate"])
            if played_day >= game_day or row.get("teamAbbrev") != team:
                continue
            minutes = _toi(row.get("toi"))
            if minutes is None:
                continue
            rows.append({"date": played_day, "minutes": minutes})
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda row: row["date"])
    return rows, source


def _training_ratio(episode, rows, cutoff_day):
    injury_day = episode["injury_report_day"]
    projected_return = episode["projected_return_day"]
    if projected_return >= cutoff_day:
        return None
    actual_returns = [row for row in rows if projected_return <= row["date"] < cutoff_day]
    if not actual_returns:
        return None
    actual_return_day = actual_returns[0]["date"]
    pre = [row["minutes"] for row in rows if row["date"] < injury_day]
    post = [row["minutes"] for row in rows if actual_return_day <= row["date"] < cutoff_day]
    if len(pre) < 5 or len(post) < 3:
        return None
    baseline = sum(pre[-5:]) / 5
    recovered = sum(post[:3]) / 3
    if baseline <= 0:
        return None
    days_out = (actual_return_day - injury_day).days
    if days_out < 1:
        return None
    return {"player_id": episode["player_id"], "team": episode["team"],
            "days_out": days_out, "band": _band(days_out),
            "minutes_ratio": min(1.5, max(0.0, recovered / baseline)),
            "baseline_minutes": baseline, "first_three_return_minutes": post[:3],
            "actual_return_day": actual_return_day.isoformat()}


def _cohort(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["band"], []).append(row)
    result = {}
    for band in ("1-3", "4-7", "8-14", "15+"):
        sample = grouped.get(band, [])
        players = len({row["player_id"] for row in sample})
        ratio = median(row["minutes_ratio"] for row in sample) if sample else None
        enough = players >= MIN_RETURNING_PLAYERS
        factor = None
        if enough and ratio is not None:
            shrunk = 1.0 + (ratio - 1.0) * len(sample) / (len(sample) + SHRINK_PRIOR_EPISODES)
            factor = round(min(1.0, max(MINUTES_FLOOR, shrunk)), 5)
        result[band] = {
            "episodes": len(sample), "distinct_players": players,
            "median_first_three_to_preinjury_minutes_ratio": round(ratio, 5) if ratio is not None else None,
            "minutes_factor": factor,
            "status": "eligible_experimental_adjustment" if enough else "insufficient_return_history",
        }
    return result


def build(history_dir, current_report, player_history, raw_history):
    if current_report.get("kind") != "nhl_pregame_player_evidence_v1":
        raise ValueError("Dated NHL pregame report required")
    if player_history.get("kind") != "nhl_skater_history_capture_v1":
        raise ValueError("Official NHL skater history required")
    histories = _snapshots(history_dir, current_report["_path"], current_report["as_of_utc"])
    completed_by_team = {}
    open_by_team = {}
    for team, snapshots in histories.items():
        completed_by_team[team], open_by_team[team] = _episodes(snapshots)
    results = []
    for game in current_report.get("games", []):
        game_day = _day(game["start_utc"])
        game_start = game["start_utc"]
        game_id = str(game["game_id"])
        sides = {}
        for team in (game["home"], game["away"]):
            snapshots = histories.get(team, [])
            # Return events closed by this exact current pregame lineup are candidates.
            current_snapshot = next((row for row in snapshots if row["game_id"] == game_id), None)
            current_active = current_snapshot["active"] if current_snapshot else {}
            all_episodes = completed_by_team.get(team, [])
            candidates = []
            for episode in all_episodes:
                pid = episode["player_id"]
                if pid not in current_active or episode["projected_return_day"] > game_day:
                    continue
                rows, _ = _player_rows(pid, team, player_history, raw_history, game_day, game_start)
                appearances_since_return = sum(
                    1 for row in rows if episode["projected_return_day"] <= row["date"] < game_day
                )
                if appearances_since_return < 3:
                    candidates.append(episode)
            episodes = []
            per_player_rows = {}
            source_manifest = []
            for episode in all_episodes:
                rows, source = _player_rows(episode["player_id"], team, player_history,
                                            raw_history, game_day, game_start)
                if source:
                    source_manifest.append({
                        "url": source.get("url"), "sha256": source.get("sha256"),
                        "retrieved_at_utc": source.get("retrieved_at"),
                    })
                    ratio = _training_ratio(episode, rows, game_day)
                    if ratio:
                        episodes.append(ratio)
                per_player_rows[episode["player_id"]] = rows
            cohort = _cohort(episodes)
            player_outputs = {}
            for episode in candidates:
                pid = episode["player_id"]
                rows = per_player_rows.get(pid, [])
                # Keep the empirical first-three-appearance ramp active only while
                # the player remains projected active and fewer than three games have
                # been logged since the first projected return.
                appearances_since_return = sum(
                    1 for row in rows if episode["projected_return_day"] <= row["date"] < game_day
                )
                if appearances_since_return >= 3:
                    continue
                days_out = (episode["projected_return_day"] - episode["injury_report_day"]).days
                if days_out < 1:
                    continue
                band = _band(days_out)
                summary = cohort[band]
                applied = summary["status"] == "eligible_experimental_adjustment" and summary["minutes_factor"] is not None and summary["minutes_factor"] < 0.995
                for evidence in (episode.get("injury_source"), episode.get("projected_return_source")):
                    if evidence and evidence not in source_manifest:
                        source_manifest.append(evidence)
                player_outputs[str(pid)] = {
                    "player_id": pid, "name": episode["name"],
                    "status": "adjustment_applied" if applied else summary["status"],
                    "injury_report_day": episode["injury_report_day"].isoformat(),
                    "days_out": days_out, "duration_band": band,
                    "minutes_factor": summary["minutes_factor"] if applied else 1.0,
                    "historical_episodes": summary["episodes"],
                    "historical_players": summary["distinct_players"],
                    "median_return_minutes_ratio": summary["median_first_three_to_preinjury_minutes_ratio"],
                    "source_type": "dated_NHL_editorial_injury_report_and_official_player_game_log",
                }
            sides[team] = {
                "status": "adjustment_applied" if any(p["status"] == "adjustment_applied" for p in player_outputs.values())
                          else "no_supported_adjustment",
                "players": player_outputs,
                "cohorts": cohort,
                "historical_return_episodes_used": sum(item["episodes"] for item in cohort.values()),
                "source_manifest": source_manifest,
            }
        results.append({"game_id": game_id, "home": game["home"], "away": game["away"],
                        "start_utc": game_start, "teams": sides})
    return {
        "kind": "nhl_return_to_play_v1",
        "as_of_utc": current_report["as_of_utc"],
        "date": current_report.get("date"),
        "games": results,
        "minimum_distinct_players_per_duration_band": MIN_RETURNING_PLAYERS,
        "applied_to_probability": any(side["status"] == "adjustment_applied"
                                      for game in results for side in game["teams"].values()),
        "calibrated": False,
        "limitations": [
            "Injuries require an explicit dated NHL.com lineup report; lineup absence alone is never treated as injury.",
            "A projected return is not a confirmed medical clearance or confirmed game participation.",
            "Minutes factor is pooled by time since injury report, shrunk toward 1.0, and capped at no increase.",
            "At least 20 distinct historical players in a duration band are required; otherwise minutes are unchanged.",
            "Experimental historical return evidence is not medically validated or calibrated.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("history-dir", "current-report", "player-history", "raw-history", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    current_path = Path(args.current_report)
    current = json.loads(current_path.read_text())
    current["_path"] = str(current_path)
    history = json.loads(Path(args.player_history).read_text())
    with gzip.open(args.raw_history, "rt", encoding="utf-8") as source:
        raw = json.load(source)
    result = build(args.history_dir, current, history, raw)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"games": len(result["games"]),
                      "adjusted_players": sum(len([p for p in side["players"].values()
                                                    if p["status"] == "adjustment_applied"])
                                                for game in result["games"] for side in game["teams"].values()),
                      "applied_to_probability": result["applied_to_probability"],
                      "calibrated": False}))


if __name__ == "__main__":
    main()
