"""Point-in-time NBA player matchup research candidate.

Historical attacker/defender production is joined to the projected five by
position. Pairings are estimates, never reported as confirmed defensive
assignments. The adjustment remains a bounded, uncalibrated candidate.
"""
import argparse
import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import time

import requests

URL = "https://stats.nba.com/stats/leagueseasonmatchups"
TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}
POSITION_GROUP = {"PG": "G", "SG": "G", "G": "G", "SF": "F", "PF": "F", "F": "F", "C": "C"}
MIN_PAIR_POSSESSIONS = 10.0
MIN_MATCHUPS_PER_TEAM = 3
MAX_LOG_ODDS_DELTA = 0.15
SEASONS = 2


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("Explicit UTC timestamp required")
    return parsed.astimezone(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _season_pair(season):
    start = int(str(season).split("-")[0])
    return [f"{start-i}-{(start-i+1)%100:02d}" for i in range(SEASONS)]


def _result_rows(payload):
    sets = payload.get("resultSets") or payload.get("resultSet")
    if isinstance(sets, dict):
        sets = [sets]
    if not isinstance(sets, list):
        raise ValueError("NBA Stats response has no result set")
    result = next((item for item in sets if str(item.get("name", "")).casefold() in
                   ("seasonmatchups", "leagueseasonmatchups")), sets[0])
    headers, rows = result.get("headers"), result.get("rowSet")
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise ValueError("NBA Stats matchup rows are malformed")
    normalized = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(headers):
            continue
        item = dict(zip(headers, row))
        try:
            off_id, def_id = str(int(item["OFF_PLAYER_ID"])), str(int(item["DEF_PLAYER_ID"]))
            poss, points = float(item["PARTIAL_POSS"]), float(item["PLAYER_PTS"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(poss) or poss <= 0 or not math.isfinite(points) or points < 0:
            continue
        normalized.append({"off_player_id": off_id, "def_player_id": def_id,
                           "partial_possessions": poss, "player_points": points,
                           "games": int(item.get("GP") or 0),
                           "matchup_minutes": str(item.get("MATCHUP_MIN") or ""),
                           "season": str(item.get("SEASON_ID") or "")})
    return normalized


def capture(snapshot, session=None, season=None):
    """Fetch only historical pair data for the teams in this pregame slate."""
    observed = datetime.now(timezone.utc).isoformat()
    start_year = int(season or snapshot.get("season_start_year") or observed[:4])
    season_label = f"{start_year}-{(start_year + 1) % 100:02d}"
    client = session or requests.Session()
    games = {}
    for game in snapshot.get("predictions", []):
        gid = str(game["game_id"])
        home, away = game["home_team"], game["away_team"]
        pair = {"home_team": home, "away_team": away, "directions": []}
        for off_team, def_team in ((home, away), (away, home)):
            off_id, def_id = TEAM_IDS.get(off_team), TEAM_IDS.get(def_team)
            if not off_id or not def_id:
                pair["directions"].append({"off_team": off_team, "def_team": def_team,
                                           "status": "unknown_team_identity", "rows": []})
                continue
            rows, errors = [], []
            for year in _season_pair(season_label):
                params = {"LeagueID": "00", "PerMode": "Totals", "Season": year,
                          "SeasonType": "Regular Season", "OffTeamID": off_id,
                          "DefTeamID": def_id, "OffPlayerID": "", "DefPlayerID": ""}
                try:
                    response = client.get(URL, params=params, timeout=25, headers={
                        "User-Agent": "Mozilla/5.0 BeatBetano pregame matchup evidence",
                        "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com",
                        "Accept": "application/json, text/plain, */*"})
                    response.raise_for_status()
                    rows.extend(_result_rows(response.json()))
                except (requests.RequestException, ValueError, TypeError):
                    errors.append(year)
                time.sleep(0.15)
            pair["directions"].append({"off_team": off_team, "def_team": def_team,
                "status": "available" if rows else "failed" if errors else "empty",
                "rows": rows, "failed_seasons": errors})
        games[gid] = pair
    status = "available" if games and all(
        all(direction["status"] == "available" for direction in game["directions"])
        for game in games.values()) else "partial" if any(
        direction["status"] == "available" for game in games.values()
        for direction in game["directions"]) else "failed"
    return {"schema_version": 1, "provider": "nba_stats_leagueseasonmatchups",
            "source_url": URL, "season": season_label, "observed_at_utc": observed,
            "status": status, "games": games, "no_odds_input": True}


def _group(position):
    return POSITION_GROUP.get(str(position or "").upper())


def _position_cost(a, b):
    x, y = _group(a), _group(b)
    if not x or not y:
        return 3
    if x == y:
        return 0
    return 1 if {x, y} in ({"G", "F"}, {"F", "C"}) else 2


def assign_by_position(offense, defense):
    """Return a minimum-position-distance estimate, never a confirmed assignment."""
    if len(offense) != 5 or len(defense) != 5:
        return []
    best = min(itertools.permutations(defense),
        key=lambda perm: (sum(_position_cost(o.get("position"), d.get("position"))
                              for o, d in zip(offense, perm)),
                         tuple(str(d.get("player_id")) for d in perm)))
    return [{"offense": o, "defense": d,
             "position_cost": _position_cost(o.get("position"), d.get("position")),
             "assignment_verified": False}
            for o, d in zip(offense, best)]


def _pair_stats(rows):
    pairs, offense = {}, {}
    for row in rows:
        off, de = str(row.get("off_player_id") or ""), str(row.get("def_player_id") or "")
        poss, points = row.get("partial_possessions"), row.get("player_points")
        if not off or not de or not _number(poss) or poss <= 0 or not _number(points) or points < 0:
            continue
        for bucket in (pairs.setdefault((off, de), [0.0, 0.0]),
                       offense.setdefault(off, [0.0, 0.0])):
            bucket[0] += float(points)
            bucket[1] += float(poss)
    return pairs, offense


def _history_margins(history, cutoff):
    rows = history if isinstance(history, list) else history.get("games", [])
    values = []
    for row in rows:
        try:
            start = utc(row["tipoff_utc"])
            observed = utc(row.get("observed_at_utc", row["tipoff_utc"]))
            home, away = row["home_points"], row["away_points"]
        except (KeyError, TypeError, ValueError):
            continue
        if start >= cutoff or observed > cutoff or not _number(home) or not _number(away):
            continue
        values.append((start, float(home) - float(away)))
    values.sort(key=lambda item: item[0])
    return [value for _, value in values[-1000:]]


def _lineups(module_context, gid, home, away):
    data = module_context.get("games", {}).get(gid, {}).get("player_matchups", {}).get("data", {})
    teams = data.get("teams", {})
    selected = {}
    for team, opponent in ((home, away), (away, home)):
        source = teams.get(team, {})
        starters = source.get("reported_starters", [])
        if source.get("lineup_status") not in ("projected", "confirmed") or len(starters) != 5:
            return None, "five_source_lineup_players_required:" + team
        if not source.get("lineup_source", "").lower().endswith("rotowire.com"):
            return None, "lineup_source_unverified:" + team
        cleaned = []
        for player in starters:
            pid, position = player.get("player_id"), player.get("position")
            if not pid or not _group(position):
                return None, "starter_identity_or_position_unresolved:" + team
            cleaned.append({"player_id": str(pid), "player": player.get("player"),
                            "position": str(position).upper()})
        if len({x["player_id"] for x in cleaned}) != 5:
            return None, "duplicate_starter_identity:" + team
        selected[team] = cleaned
    return selected, None


def build(snapshot, module_context, matchup_data, history):
    for document in (snapshot, module_context):
        if document.get("content_sha256") != digest(
            {k: v for k, v in document.items() if k != "content_sha256"}):
            raise ValueError("Input digest mismatch")
    seal = snapshot["content_sha256"]
    if module_context.get("snapshot_sha256") != seal:
        raise ValueError("Module context does not match frozen snapshot")
    if matchup_data.get("provider") != "nba_stats_leagueseasonmatchups":
        raise ValueError("Unexpected matchup data provider")
    captured = utc(matchup_data.get("observed_at_utc"))
    issued = utc(snapshot["created_at_utc"])
    if captured > issued:
        raise ValueError("Matchup evidence was captured after forecast issue")
    margins = _history_margins(history, issued)
    scale = None
    if len(margins) >= 100:
        mean = sum(margins) / len(margins)
        sd = math.sqrt(sum((x - mean) ** 2 for x in margins) / len(margins))
        if sd > 0 and math.isfinite(sd):
            scale = sd * math.sqrt(3.0) / math.pi
    output = []
    for fixture in snapshot.get("predictions", []):
        gid = str(fixture["game_id"])
        base = fixture.get("hybrid_p_home")
        row = {"game_id": gid, "home_team": fixture["home_team"],
               "away_team": fixture["away_team"], "base_home_probability": base,
               "adjusted_home_probability": None, "status": "blocked", "reason": None,
               "applied": False, "assignment_method": "minimum_position_distance_estimate",
               "assignments_verified": False, "teams": {},
               "margin_sample_games": len(margins), "logistic_margin_scale_points": scale,
               "calibrated": False, "production_approved": False}
        if not _number(base) or not 0 < base < 1:
            row["reason"] = "invalid_baseline_probability"; output.append(row); continue
        if scale is None:
            row["reason"] = "fewer_than_100_pre_issue_margin_games"; output.append(row); continue
        games = matchup_data.get("games", {})
        captured_game = games.get(gid, {})
        directions = captured_game.get("directions", [])
        if len(directions) != 2 or any(d.get("status") != "available" for d in directions):
            row["reason"] = "head_to_head_matchup_source_unavailable"; output.append(row); continue
        selected, reason = _lineups(module_context, gid, fixture["home_team"], fixture["away_team"])
        if reason:
            row["reason"] = reason; output.append(row); continue
        by_direction = {(d["off_team"], d["def_team"]): d["rows"] for d in directions}
        team_delta = {}
        failed = False
        for offense_team, defense_team in ((fixture["home_team"], fixture["away_team"]),
                                           (fixture["away_team"], fixture["home_team"])):
            assignments = assign_by_position(selected[offense_team], selected[defense_team])
            raw_rows = by_direction.get((offense_team, defense_team), [])
            pairs, baselines = _pair_stats(raw_rows)
            details, residuals = [], []
            for assignment in assignments:
                off = str(assignment["offense"]["player_id"])
                de = str(assignment["defense"]["player_id"])
                pair = pairs.get((off, de))
                overall = baselines.get(off)
                pair_poss = pair[1] if pair else 0.0
                if pair and overall and pair_poss >= MIN_PAIR_POSSESSIONS and overall[1] >= 40:
                    residual = pair[0] / pair[1] - overall[0] / overall[1]
                    residuals.append(residual)
                    status = "historical_pair_sample_usable"
                else:
                    residual = None
                    status = "insufficient_historical_pair_sample"
                details.append({"offense_player": assignment["offense"],
                    "defender_player": assignment["defense"], "position_cost": assignment["position_cost"],
                    "assignment_verified": False, "partial_possessions": round(pair_poss, 2),
                    "points_per_partial_possession_residual": round(residual, 5) if residual is not None else None,
                    "status": status})
            row["teams"][offense_team] = {"opponent": defense_team,
                "usable_pairs": len(residuals), "required_pairs": MIN_MATCHUPS_PER_TEAM,
                "points_delta_per_100_possessions": None, "assignments": details}
            if len(residuals) < MIN_MATCHUPS_PER_TEAM:
                failed = True
            else:
                coverage = len(residuals) / 5.0
                team_delta[offense_team] = sum(residuals) / len(residuals) * 100.0 * coverage
                row["teams"][offense_team]["points_delta_per_100_possessions"] = round(team_delta[offense_team], 4)
        if failed:
            row["reason"] = "fewer_than_three_supported_starter_matchups_per_team"
            output.append(row); continue
        margin_delta = team_delta[fixture["home_team"]] - team_delta[fixture["away_team"]]
        log_delta = max(-MAX_LOG_ODDS_DELTA, min(MAX_LOG_ODDS_DELTA, margin_delta / scale))
        logit = math.log(base / (1.0 - base))
        adjusted = 1.0 / (1.0 + math.exp(-(logit + log_delta)))
        row.update({"status": "research_scenario", "reason": None,
                    "estimated_home_margin_delta_per_100_possessions": round(margin_delta, 4),
                    "log_odds_delta": round(log_delta, 6),
                    "adjusted_home_probability": adjusted,
                    "applied": not math.isclose(adjusted, base, rel_tol=0, abs_tol=1e-12)})
        output.append(row)
    body = {"schema_version": 1, "snapshot_sha256": seal,
            "created_at_utc": snapshot["created_at_utc"],
            "source_observed_at_utc": matchup_data.get("observed_at_utc"),
            "games": output, "calibrated": False, "production_approved": False,
            "assignments_verified": False, "no_odds_input": True}
    body["content_sha256"] = digest(body)
    return body


def _load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--snapshot", required=True)
    capture_parser.add_argument("--output", required=True)
    capture_parser.add_argument("--season", type=int)
    predict_parser = sub.add_parser("predict")
    for name in ("snapshot", "module-context", "matchups", "history", "output"):
        predict_parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "capture":
        result = capture(_load(args.snapshot), season=args.season)
        target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, allow_nan=False))
        print(json.dumps({"status": result["status"], "games": len(result["games"]),
                          "source": result["source_url"]}))
        return
    result = build(_load(args.snapshot), _load(args.module_context),
                   _load(args.matchups), _load(args.history))
    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({"games": len(result["games"]),
                      "applied": sum(row["applied"] for row in result["games"]),
                      "calibrated": False}))


if __name__ == "__main__":
    main()
