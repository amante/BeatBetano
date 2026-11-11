"""Explain official NBA injury claims as a conditional minutes/production scenario.

The output is a research sidecar. It uses exact roster IDs, actual past box-score
rows and a capped 240-minute allocation; it never changes baseline probabilities
or describes unreported players as confirmed active.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from rotation_allocation_adapter import project_nba_minutes

STAT_FIELDS = ("points", "rebounds", "assists", "turnovers")
MIN_HISTORY = 3
MIN_MINUTE_HISTORY = 2
MAX_HISTORY = 5
OFFICIAL_CONFIDENCE = "official_nba_injury_report_unique_roster_match"
NORMALIZED = {
    "out": "out", "inactive": "out", "suspended": "out", "ruled out": "out",
    "questionable": "questionable", "doubtful": "doubtful", "probable": "probable",
    "available": "available", "active": "available",
}


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def _official_claims(player, emitted_at, tipoff):
    claims = []
    for source in player.get("status_sources", []):
        if source.get("confidence") != OFFICIAL_CONFIDENCE:
            continue
        host = urlparse(str(source.get("url", ""))).hostname
        if host not in ("ak-static.cms.nba.com", "official.nba.com"):
            continue
        try:
            observed = utc(source.get("observed_at_utc"))
            if observed > utc(emitted_at) or observed >= utc(tipoff):
                continue
            reported = utc(source.get("reported_at_utc"))
            if reported > observed:
                continue
        except (TypeError, ValueError):
            continue
        status = NORMALIZED.get(str(source.get("status", "")).strip().casefold())
        if status is None:
            continue
        claims.append({"status": status, "source_url": source.get("url"),
                       "reported_at_utc": source.get("reported_at_utc"),
                       "observed_at_utc": source.get("observed_at_utc")})
    unique = {(claim["status"], claim["source_url"], claim["observed_at_utc"]): claim
              for claim in claims}
    return list(unique.values())


def _history_by_player(rows, team, emitted_at, tipoff):
    grouped = defaultdict(list)
    for row in rows:
        if row.get("team") != team or not row.get("player_id"):
            continue
        try:
            event = utc(row["tipoff_utc"])
            observed = utc(row["observed_at_utc"])
            if event >= utc(tipoff) or observed > utc(emitted_at):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if (row.get("did_not_play") or type(row.get("minutes_played")) not in (int, float)
                or row["minutes_played"] <= 0):
            continue
        grouped[str(row["player_id"])].append(row)
    result = {}
    for pid, sample in grouped.items():
        sample.sort(key=lambda item: utc(item["tipoff_utc"]))
        sample = sample[-MAX_HISTORY:]
        rates = {}
        for field in STAT_FIELDS:
            values = [row.get(field) for row in sample]
            valid = [value for value in values if type(value) in (int, float)
                     and math.isfinite(value) and value >= 0]
            rates[field] = round(sum(valid) / len(valid), 3) if len(valid) >= MIN_HISTORY else None
        valid_minutes = [row["minutes_played"] for row in sample
                         if type(row["minutes_played"]) in (int, float)
                         and math.isfinite(row["minutes_played"]) and row["minutes_played"] > 0]
        minute_count = len(valid_minutes)
        result[pid] = {"sample_games": len(sample), "average_minutes":
                       round(sum(valid_minutes) / minute_count, 2)
                       if minute_count >= MIN_MINUTE_HISTORY else None,
                       "minutes_sample_games": minute_count,
                       "minutes_estimate_confidence": ("moderate" if minute_count >= 4 else
                                                       "limited" if minute_count >= MIN_MINUTE_HISTORY else None),
                       "minutes_estimate_method": "mean_last_5_observed_appearances"
                       if minute_count >= MIN_MINUTE_HISTORY else None,
                       "per_game": rates,
                       "observed_through_utc": max(row["observed_at_utc"] for row in sample)}
    return result


def _allocations(team, rotation_team, out_ids, history_by_player, out_players, starter_evidence=None):
    samples = {str(row.get("player_id")): row for row in rotation_team.get("provisional_rotation", [])
               if row.get("player_id") and type(row.get("minutes_projection")) in (int, float)
               and math.isfinite(row["minutes_projection"]) and row["minutes_projection"] >= 0}
    # Officially OUT players can be absent from the recent rotation list
    # precisely because they have been unavailable. Recover their weight from
    # pre-tipoff appearances in the longer current-season sample.
    out_by_id = {str(row["player_id"]): row for row in out_players}
    for pid in sorted(out_ids - set(samples)):
        historical = history_by_player.get(pid, {})
        estimate = historical.get("average_minutes")
        if (type(estimate) in (int, float) and math.isfinite(estimate)
                and estimate > 0 and historical.get("minutes_sample_games", 0) >= MIN_MINUTE_HISTORY):
            samples[pid] = {"player_id": pid,
                            "player": out_by_id.get(pid, {}).get("player"),
                            "minutes_projection": estimate,
                            "sample_games": historical.get("minutes_sample_games", 0),
                            "projection_method": historical.get("minutes_estimate_method")}
    starter_evidence = starter_evidence or {"status": "lineup_source_unavailable", "weights": {}, "players": []}
    from starting_lineup_minutes import apply_role_weights
    starter_details = {str(row.get("player_id")): row for row in starter_evidence.get("players", [])}
    starter_applied = apply_role_weights(samples, starter_evidence, history_by_player)
    missing_out = sorted(out_ids - set(samples))
    if missing_out:
        return {"status": "out_player_missing_minute_estimate", "missing_out_player_ids": missing_out,
                "missing_out_players": [{"player_id": pid,
                                         "player": out_by_id.get(pid, {}).get("player")}
                                        for pid in missing_out],
                "minimum_required_appearances": MIN_MINUTE_HISTORY,
                "baseline": None, "conditional": None, "changes": []}
    if not samples:
        return {"status": "no_reliable_minute_history", "baseline": None,
                "conditional": None, "changes": []}

    def allocate(excluded):
        candidates = [{"player_id": pid, "status": "out" if pid in excluded else "available",
                      "expected_weight": row["minutes_projection"], "max_units": 48}
                     for pid, row in sorted(samples.items())]
        return project_nba_minutes({"roster_complete": True,
                                    "availability_source_verified": True,
                                    "players": candidates})

    baseline = allocate(set())
    conditional = allocate(out_ids)
    if baseline.get("allocations") is None or conditional.get("allocations") is None:
        return {"status": "minute_allocation_infeasible", "baseline": baseline,
                "conditional": conditional, "changes": []}
    changes = []
    for pid, row in sorted(samples.items()):
        before = baseline["allocations"].get(pid, 0.0)
        after = conditional["allocations"].get(pid, 0.0)
        changes.append({"player_id": pid, "player": row.get("player"),
                        "historical_minutes_projection": row["minutes_projection"],
                        "projection_method": row.get("projection_method"),
                        "baseline_minutes": before, "scenario_minutes": after,
                        "minute_delta": round(after - before, 3),
                        "sample_games": row.get("sample_games", 0),
                        "position_abbreviation": row.get("position_abbreviation"),
                        "lineup_role_weight_applied": row.get("lineup_role_weight_applied", False),
                        "role_is_confirmed": False})
    return {"status": "conditional_historical_rotation_scenario",
            "baseline": baseline, "conditional": conditional, "changes": changes,
            "lineup_role_weights_applied": len(starter_applied),
            "lineup_role_players": [starter_details[pid] for pid in starter_applied],
            "lineup_evidence_status": starter_evidence.get("status"),
            "lineup_source_url": starter_evidence.get("source_url")}


def _team_impact(team, roster, rotation_team, history, emitted_at, tipoff, report_diagnostic):
    players = roster.get("players", [])
    by_id = {str(player.get("player_id")): player for player in players if player.get("player_id")}
    samples = _history_by_player(history, team, emitted_at, tipoff)
    explicit = []
    conflicted = []
    out_ids = set()
    for pid, player in by_id.items():
        claims = _official_claims(player, emitted_at, tipoff)
        states = sorted({claim["status"] for claim in claims})
        if not claims:
            continue
        row = {"player_id": pid, "player": player.get("player"),
               "official_status": states[0] if len(states) == 1 else "conflicting_official_claims",
               "official_status_sources": claims,
               "historical": samples.get(pid)}
        if len(states) != 1:
            conflicted.append(row)
            continue
        explicit.append(row)
        if states[0] == "out":
            out_ids.add(pid)

    losses = {field: 0.0 for field in STAT_FIELDS}
    unsupported = []
    for row in explicit:
        if row["official_status"] != "out":
            continue
        historical = row.get("historical")
        if not historical or historical.get("average_minutes") is None:
            unsupported.append(row["player_id"])
            continue
        row["estimated_minutes_lost"] = historical["average_minutes"]
        row["estimated_minutes_sample_games"] = historical.get("minutes_sample_games", 0)
        row["estimated_minutes_confidence"] = historical.get("minutes_estimate_confidence")
        row["estimated_minutes_method"] = historical.get("minutes_estimate_method")
        for field in STAT_FIELDS:
            value = historical["per_game"].get(field)
            if value is None:
                unsupported.append(row["player_id"] + ":" + field)
            else:
                losses[field] += value
    out_players = [row for row in explicit if row["official_status"] == "out"]
    starter_evidence = {"status": "lineup_source_unavailable", "weights": {}, "players": []}
    if out_ids:
        from starting_lineup_minutes import estimate as estimate_starter_minutes
        starter_evidence = estimate_starter_minutes(team, roster, history, emitted_at, tipoff)
        if out_ids.intersection(starter_evidence.get("weights", {})):
            starter_evidence = {"status": "official_injury_conflicts_with_reported_starters",
                                "weights": {}, "players": []}
    allocation = _allocations(team, rotation_team, out_ids, samples, out_players, starter_evidence) if out_ids else {
        "status": "no_official_out_players", "baseline": None,
        "conditional": None, "changes": [], "lineup_role_weights_applied": 0,
        "lineup_evidence_status": "no_official_out_players"}

    change_by_id = {row["player_id"]: row for row in allocation["changes"]}
    redistributed = {field: 0.0 for field in STAT_FIELDS}
    missing_recipient_history = []
    for pid, change in change_by_id.items():
        delta = change["minute_delta"]
        if delta <= 0:
            continue
        historical = samples.get(pid)
        if not historical:
            missing_recipient_history.append(pid)
            continue
        for field in STAT_FIELDS:
            per_game = historical["per_game"].get(field)
            minutes = historical.get("average_minutes")
            if per_game is None or not minutes:
                missing_recipient_history.append(pid + ":" + field)
                continue
            amount = delta * per_game / minutes
            redistributed[field] += amount
            change.setdefault("historical_output_delta_per_game", {})[field] = round(amount, 3)

    unknown_statuses = sum(player.get("status") in ("unknown", "questionable", "doubtful")
                           for player in players)
    return {"team": team, "roster_complete": roster.get("roster_complete") is True,
            "official_report_capture_status": report_diagnostic.get("status", "report_not_retrieved"),
            "official_report_fixture_rows": report_diagnostic.get("fixture_team_rows", 0),
            "official_reported_players": explicit, "conflicting_official_claims": conflicted,
            "official_out_count": len(out_ids), "historical_output_loss_per_game":
                {key: round(value, 2) for key, value in losses.items()},
            "players_without_historical_minutes": sorted(set(unsupported)),
            "minute_redistribution": allocation,
            "historical_output_from_added_minutes_per_game":
                ({key: round(value, 2) for key, value in redistributed.items()}
                 if allocation["status"] == "conditional_historical_rotation_scenario" else None),
            "replacement_history_gaps": sorted(set(missing_recipient_history)),
            "players_without_confirmed_availability": unknown_statuses,
            "scenario_assumption": "Only players explicitly reported OUT are removed; remaining historical rotation candidates are conditional replacements, not confirmed active players.",
            "all_player_changes_are_research_estimates": True}


def build(snapshot, availability, rotation, player_history, emitted_at=None):
    seal = snapshot.get("content_sha256")
    if not seal or availability.get("snapshot_sha256") != seal or rotation.get("snapshot_sha256") != seal:
        raise ValueError("Injury/rotation evidence belongs to another baseline snapshot")
    emitted_at = emitted_at or datetime.now(timezone.utc).isoformat()
    if utc(emitted_at) < utc(snapshot["created_at_utc"]):
        raise ValueError("Impact scenario predates the baseline")
    # Archived player-game history is a JSON array; accept the older wrapper too.
    if isinstance(player_history, list):
        history_rows = player_history
    elif isinstance(player_history, dict):
        rows = player_history.get("players", [])
        history_rows = rows if isinstance(rows, list) else []
    else:
        history_rows = []
    result = {}
    for game in snapshot.get("predictions", []):
        gid = str(game["game_id"])
        tipoff = game["tipoff_utc"]
        if utc(emitted_at) >= utc(tipoff):
            result[gid] = {"status": "pregame_window_closed", "emitted_at_utc": emitted_at, "teams": {}}
            continue
        availability_game = availability.get("games", {}).get(gid, {}).get("teams", {})
        rotation_game = rotation.get("games", {}).get(gid, {}).get("teams", {})
        official_evidence = availability.get("official_report_evidence", {})
        diagnostic = next((row for row in official_evidence.get("rows_by_fixture", [])
                           if str(row.get("game_id")) == gid), {})
        teams = {}
        for team in (game["home_team"], game["away_team"]):
            roster = availability_game.get(team, {})
            team_rotation = rotation_game.get(team, {})
            teams[team] = _team_impact(team, roster, team_rotation,
                                       history_rows, emitted_at, tipoff,
                                       diagnostic)
        result[gid] = {"status": "research_only", "emitted_at_utc": emitted_at, "teams": teams,
                       "probabilities_adjusted": False,
                       "baseline_snapshot_sha256": seal}
    return {"model_version": "NBA_OFFICIAL_INJURY_IMPACT_RESEARCH_V1",
            "baseline_snapshot_sha256": seal, "emitted_at_utc": emitted_at,
            "games": result, "calibrated": False, "production_approved": False,
            "baseline_probabilities_changed": False,
            "note": "Historical minute and box-score rates create a conditional sensitivity scenario only; no injured-player effect is causal or a production probability adjustment."}


def main():
    parser = argparse.ArgumentParser()
    for arg in ("snapshot", "availability", "rotation", "player-history", "output"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    report = build(load(args.snapshot), load(args.availability), load(args.rotation),
                   load(args.player_history))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"games": len(report["games"]), "probabilities_adjusted": False,
                      "out_players": sum(team["official_out_count"]
                          for game in report["games"].values()
                          for team in game.get("teams", {}).values())}))


if __name__ == "__main__":
    main()
