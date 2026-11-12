"""Reissue a frozen NBA baseline after evidence capture and connect modules.

The resulting snapshot uses the same history and probabilities as the seed for
still-pregame fixtures, but its issue time follows the captured evidence. The
supporting modules are included in the final slate without changing probabilities.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from prospective import generate, utc
from active_roster_resolver import resolve
from player_status_intake import reconcile
from rotation_efficiency_report import build as build_rotation
from joint_minutes_report import build as build_minutes
from availability_scenarios import scenarios as build_scenarios
from official_injury_impact import build as build_injury_impact
from roster_matchups import evaluate as build_roster_matchups
from availability_impact import build as build_availability_features
from travel_context import build as build_travel


def read(path, default=None):
    if not path or not Path(path).is_file():
        return default if default is not None else {}
    return json.loads(Path(path).read_text())


def write_new(path, value):
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as out: json.dump(value, out, indent=2, sort_keys=True, allow_nan=False)


def rebind(source, seed_sha, issued_sha):
    value = dict(source or {})
    actual = value.get("snapshot_sha256")
    if actual != seed_sha:
        raise ValueError("Raw module evidence does not belong to the seed fixture snapshot")
    value["source_snapshot_sha256"] = actual
    value["snapshot_sha256"] = issued_sha
    value["rebound_for_issued_snapshot"] = True
    return value


def _name_key(value):
    import unicodedata
    return " ".join("".join(ch for ch in unicodedata.normalize("NFKD", str(value or "")).casefold()
                             if not unicodedata.combining(ch)).split())


def player_matchup_context(snapshot, roster_feed, lineups):
    games = {}
    for fixture in snapshot["predictions"]:
        gid = str(fixture["game_id"]); teams = {}
        lineup_game = lineups.get("games", {}).get(gid, {}).get("teams", {})
        roster_game = roster_feed.get("games", {}).get(gid, {}).get("teams", {})
        for team in (fixture["home_team"], fixture["away_team"]):
            lineup = lineup_game.get(team, {})
            roster = roster_game.get(team, {})
            by_name = {}
            for player in roster.get("players", []):
                by_name.setdefault(_name_key(player.get("player")), []).append(player)
            starters = []
            for name in lineup.get("starters", []):
                matches = by_name.get(_name_key(name), [])
                match = matches[0] if len(matches) == 1 else None
                starters.append({"player": name,
                    "player_id": match.get("player_id") if match else None,
                    "position": match.get("position_abbreviation") if match else None,
                    "position_name": match.get("position_name") if match else None,
                    "roster_match_status": "unique_exact_name_match" if match else "unresolved_exact_name_match"})
            pos = [x["position"] for x in starters if x.get("position")]
            teams[team] = {"lineup_status": lineup.get("lineup_status", "unavailable"),
                "lineup_source": lineup.get("source_url"), "lineup_observed_at_utc": lineup.get("observed_at_utc"),
                "reported_starters": starters, "position_coverage": len(pos),
                "position_counts": {p: pos.count(p) for p in sorted(set(pos))},
                "opponent_position_counts": None,
                "defensive_assignments_verified": False}
        for team, row in teams.items():
            opponent = fixture["away_team"] if team == fixture["home_team"] else fixture["home_team"]
            row["opponent_position_counts"] = teams[opponent]["position_counts"]
        games[gid] = {"home_team": fixture["home_team"], "away_team": fixture["away_team"],
                       "teams": teams, "status": "projected_positions_only_no_assignment_source",
                       "probabilities_adjusted": False}
    return {"schema_version": 1, "snapshot_sha256": snapshot["content_sha256"],
            "games": games, "no_player_defender_pairs_inferred": True,
            "probabilities_adjusted": False}


def _same_probabilities(seed, issued):
    old = {str(p["game_id"]): p for p in seed.get("predictions", [])}
    for new in issued.get("predictions", []):
        prior = old.get(str(new["game_id"]))
        if not prior: raise ValueError("Reissued fixture was not in the seed slate")
        for key in ("elo_p_home", "challenger_p_home", "hybrid_p_home"):
            a, b = prior.get(key), new.get(key)
            if type(a) not in (int, float) or type(b) not in (int, float) or not math.isclose(a, b, rel_tol=0, abs_tol=1e-12):
                raise ValueError("Reissued snapshot changed the baseline probability: " + key)


def build(seed, history, scoreboard, game_date, roster, lineups, sporting, official, player_history):
    now = datetime.now(timezone.utc).isoformat()
    freeze = datetime.fromisoformat(now.replace('Z', '+00:00'))
    seed_games = {str(p["game_id"]): p for p in seed.get("predictions", [])}
    fixtures = []
    scoreboard_fixtures = {str(row["game_id"]): row for row in scoreboard.get("future_fixtures", [])}
    for gid, prior in seed_games.items():
        row = scoreboard_fixtures.get(gid)
        if not row: continue
        if (row["home_team"], row["away_team"], row["tipoff_utc"]) != (prior["home_team"], prior["away_team"], prior["tipoff_utc"]):
            raise ValueError("Current scoreboard identity changed from seed snapshot")
        if utc(row["tipoff_utc"]) > freeze:
            fixtures.append(row)
    if not fixtures:
        return None, {"status": "no_seed_fixtures_remain_pregame", "seed_snapshot_sha256": seed.get("content_sha256"),
                      "created_at_utc": now, "probabilities_adjusted": False}
    issued = generate(history, fixtures, now)
    _same_probabilities(seed, issued)
    seed_sha = seed.get("content_sha256"); issued_sha = issued.get("content_sha256")
    rebound_roster = rebind(roster, seed_sha, issued_sha)
    rebound_lineups = rebind(lineups, seed_sha, issued_sha)
    rebound_sporting = rebind(sporting, seed_sha, issued_sha) if sporting.get("snapshot_sha256") else dict(sporting)
    statuses = reconcile(issued, rebound_roster, rebound_sporting, official)
    availability = resolve(issued, rebound_roster, statuses, rebound_lineups)
    rotation = build_rotation(issued, history, player_history)
    minutes = build_minutes(issued, rotation, availability)
    scenarios = build_scenarios(issued, rotation, availability)
    injury_impact = build_injury_impact(issued, availability, rotation,
        player_history.get("players", []), emitted_at=issued["created_at_utc"],
        lineups=rebound_lineups)
    matchups = player_matchup_context(issued, rebound_roster, rebound_lineups)
    # Preserve the existing strict roster/matchup audit beside the richer
    # projected-position context. It remains non-verified unless human/source
    # evidence explicitly confirms positional assignments.
    verified_matchups = build_roster_matchups(issued, rebound_sporting)
    availability_features = build_availability_features(issued, verified_matchups)
    travel = build_travel(issued, history)
    modules = {}
    for fixture in issued["predictions"]:
        gid = str(fixture["game_id"])
        lineup_data = lineups.get("games", {}).get(gid, {})
        matchup_data = matchups["games"].get(gid, {})
        rotation_data = rotation.get("games", {}).get(gid, {})
        minutes_data = minutes.get("games", {}).get(gid, {})
        impact_data = injury_impact.get("games", {}).get(gid, {})
        travel_data = travel.get("games", {}).get(gid, {})
        injury_state = official.get("retrieval_status") or (
            "available" if official.get("official_document_retrieved") is True else "pending")
        if injury_state not in ("available", "pending", "failed"):
            try:
                attempt = utc(official["retrieval_attempted_at_utc"])
                release = attempt.replace(hour=10, minute=30, second=0, microsecond=0, tzinfo=timezone.utc)
                injury_state = "pending" if attempt < release else "failed"
            except (KeyError, ValueError, TypeError):
                injury_state = "pending"
        lineup_ready = any(team.get("starters") for team in lineup_data.get("teams", {}).values())
        matchup_ready = any(team.get("reported_starters") for team in matchup_data.get("teams", {}).values())
        minutes_ready = any(team.get("allocations") is not None for team in minutes_data.get("teams", {}).values())
        impact_ready = any(team.get("official_reported_players") for team in impact_data.get("teams", {}).values())
        travel_ready = any(team.get("travel_distance_km") is not None for team in travel_data.get("teams", {}).values())
        modules[gid] = {
            "statistical_baseline": {"connected": True, "affects_prediction": True,
                "status": "included", "entered_prediction": True,
                "detail": "La probabilidad estadística base sí se utilizó."},
            "official_injury_report": {"connected": True, "affects_prediction": False,
                "status": "failed" if injury_state == "failed" else "pending" if injury_state == "pending" else "available_not_used",
                "entered_prediction": False,
                "detail": official.get("retrieval_error_detail") if injury_state == "failed" else
                    "Fuente capturada, pero lesiones no cambian los porcentajes actuales." if injury_state == "available" else
                    "El informe todavía no estaba disponible al capturar."},
            "starting_lineups": {"connected": True, "affects_prediction": False,
                "status": "available_not_used" if lineup_ready else "pending",
                "entered_prediction": False, "data": lineup_data},
            "player_matchups": {"connected": True, "affects_prediction": False,
                "status": "available_not_used" if matchup_ready else "pending",
                "entered_prediction": False, "data": matchup_data},
            "rotation_minutes": {"connected": True, "affects_prediction": False,
                "status": "available_not_used" if minutes_ready else "pending",
                "entered_prediction": False, "historical_rotation": rotation_data,
                "joint_allocation": minutes_data,
                "availability_status": availability.get("games", {}).get(gid, {}),
                "availability_scenarios": scenarios.get("games", {}).get(gid, {})},
            "availability_impact": {"connected": True, "affects_prediction": False,
                "status": "available_not_used" if impact_ready else "pending",
                "entered_prediction": False, "conditional_production_scenario": impact_data,
                "feature_readiness": availability_features.get("games", {}).get(gid, {})},
            "travel_time_zones": {"connected": True, "affects_prediction": False,
                "status": "available_not_used" if travel_ready else "pending",
                "entered_prediction": False, "data": travel_data},
        }
    body = {"schema_version": 1, "snapshot_sha256": issued_sha,
        "seed_snapshot_sha256": seed_sha, "created_at_utc": issued["created_at_utc"],
        "evidence_captured_before_issue": True,
        "probabilities_modified_by_modules": False, "games": modules}
    body["content_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    summary = {"status": "reissued_baseline_with_connected_modules", "seed_snapshot_sha256": seed_sha,
        "issued_snapshot_sha256": issued_sha, "games": len(issued["predictions"]),
        "issue_after_evidence_capture": True, "baseline_probabilities_unchanged": True,
        "official_injury_document_retrieved": official.get("official_document_retrieved") is True,
        "official_matched_claims": statuses.get("official_matched_claims", 0),
        "teams_with_minutes_allocations": sum(t.get("allocations") is not None for g in minutes.get("games", {}).values() for t in g.get("teams", {}).values()),
        "player_position_entries": sum(len(t.get("reported_starters", [])) for g in matchups["games"].values() for t in g["teams"].values()),
        "travel_distance_estimates": sum(t.get("travel_distance_km") is not None for g in travel["games"].values() for t in g["teams"].values()),
        "modules_connected": ["player_matchups", "rotation_minutes", "availability_impact", "travel_time_zones"],
        "modules_affecting_probabilities": [],
        "probabilities_unchanged_from_seed": True,
        "coverage_limitations": ["Projected lineup positions do not establish defensive assignments.",
            "Only official injury claims are used for the official availability scenario; missing statuses stay unresolved.",
            "Travel distance is approximate and no travel coefficient is fitted."]}
    return issued, {"summary": summary, "context": body}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("seed-snapshot", "history", "fixtures", "date", "roster", "lineups", "sporting", "official", "players", "snapshot-output", "context-output", "summary-output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    seed = read(args.seed_snapshot); history = read(args.history, []); roster = read(args.roster)
    lineups = read(args.lineups); sporting = read(args.sporting); official = read(args.official)
    players = read(args.players, {"players": []})
    scoreboard = read(args.fixtures, {"future_fixtures": []})
    issued, result = build(seed, history, scoreboard, args.date, roster, lineups, sporting, official, players)
    write_new(args.summary_output, result["summary"] if issued else result)
    if issued:
        write_new(args.snapshot_output, issued)
        write_new(args.context_output, result["context"])
        print(json.dumps(result["summary"], indent=2))
    else:
        print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
