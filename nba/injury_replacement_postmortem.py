"""Postgame audit of pregame NBA injury and replacement-minute scenarios.

This compares frozen pregame claims and minute allocations with actual player
participation. It does not estimate causal injury effects or revise probabilities.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify(document, field="content_sha256"):
    if not isinstance(document, dict) or not isinstance(document.get(field), str):
        raise ValueError("Missing sealed document")
    body = {key: value for key, value in document.items() if key != field}
    if digest(body) != document[field]:
        raise ValueError("Document digest mismatch")


def player_rows(boxscores):
    rows = boxscores if isinstance(boxscores, list) else boxscores.get("players", [])
    if not isinstance(rows, list):
        raise ValueError("Player boxscores must contain a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        game_id = str(row.get("game_id", ""))
        player_id = str(row.get("player_id", ""))
        if not game_id or not player_id:
            continue
        key = (game_id, player_id)
        if key in result:
            raise ValueError("Duplicate player/game boxscore identity")
        result[key] = row
    return result


def claims_by_team(module_game):
    evidence = (module_game.get("injury_source_reconciliation") or {}).get("data") or {}
    teams = evidence.get("teams") or {}
    output = {}
    for team, entries in teams.items():
        output[team] = {}
        for entry in entries if isinstance(entries, list) else []:
            player_id = str(entry.get("player_id", ""))
            if not player_id:
                continue
            output[team][player_id] = {
                "player": entry.get("player"),
                "conflict": bool(entry.get("conflict")),
                "status_agreement": entry.get("status_agreement"),
                "claims": entry.get("claims", []),
            }
    return output


def lineup_starters(module_game):
    lineup = (module_game.get("starting_lineups") or {}).get("data") or {}
    teams = lineup.get("teams") or {}
    result = {}
    for team, row in teams.items():
        starters = row.get("reported_starters", [])
        result[team] = {
            "status": row.get("lineup_status") or row.get("status"),
            "source": row.get("lineup_source"),
            "players": starters if isinstance(starters, list) else [],
        }
    return result


def _team_scenario(scenario, team):
    multi = scenario.get("multi_source_scenario") or {}
    row = (multi.get("teams") or {}).get(team)
    if row is not None:
        return row
    return (scenario.get("teams") or {}).get(team, {})


def _player_audit(player_id, name, claim, out_item, change, actual):
    claims = claim.get("claims", []) if claim else []
    states = sorted({str(row.get("status", "")).casefold() for row in claims if row.get("status")})
    actual_known = actual is not None
    minutes = actual.get("minutes_played") if actual_known else None
    dnp = actual.get("did_not_play") if actual_known else None
    if actual_known and dnp is True:
        participation = "did_not_play"
    elif actual_known and type(minutes) in (int, float) and minutes > 0:
        participation = "played"
    elif actual_known and minutes == 0:
        participation = "zero_minutes"
    else:
        participation = "not_in_boxscore"
    comparisons = None
    if actual_known and type(minutes) in (int, float) and change:
        baseline = change.get("baseline_minutes")
        projected = change.get("scenario_minutes")
        if type(baseline) in (int, float) and type(projected) in (int, float):
            comparisons = {
                "actual_minus_baseline_minutes": round(minutes - baseline, 3),
                "actual_minus_scenario_minutes": round(minutes - projected, 3),
            }
    status_check = "no_claim"
    if states:
        if "out" in states:
            status_check = "out_claim_matches_dnp" if participation == "did_not_play" else (
                "out_claim_player_participated" if participation in ("played", "zero_minutes") else "out_claim_unverifiable")
        elif any(state in ("questionable", "doubtful", "probable") for state in states):
            status_check = "uncertain_claim_player_participated" if participation == "played" else (
                "uncertain_claim_player_did_not_play" if participation == "did_not_play" else "uncertain_claim_unverifiable")
        else:
            status_check = "claim_recorded"
    return {
        "player_id": player_id,
        "player": name or (claim or {}).get("player") or (out_item or {}).get("player") or (change or {}).get("player"),
        "pregame_statuses": states,
        "source_claims": claims,
        "conflict": bool((claim or {}).get("conflict")),
        "predicted_out_source_class": (out_item or {}).get("accepted_source_class"),
        "predicted_baseline_minutes": (change or {}).get("baseline_minutes"),
        "predicted_scenario_minutes": (change or {}).get("scenario_minutes"),
        "predicted_minute_delta": (change or {}).get("minute_delta"),
        "actual_participation": participation,
        "actual_minutes": minutes,
        "actual_points": actual.get("points") if actual_known else None,
        "actual_rebounds": actual.get("rebounds") if actual_known else None,
        "actual_assists": actual.get("assists") if actual_known else None,
        "actual_starter": actual.get("starter_reported_postgame") if actual_known else None,
        "minutes_comparison": comparisons,
        "status_check": status_check,
    }


def build(snapshot, injury_adjustment, module_context, boxscores, settled=None):
    verify(snapshot)
    verify(injury_adjustment)
    verify(module_context)
    snapshot_sha = snapshot.get("content_sha256")
    if injury_adjustment.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("Injury scenarios do not match the frozen snapshot")
    if module_context.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("Module context does not match the frozen snapshot")
    if set(module_context.get("games", {})) != {str(row["game_id"]) for row in snapshot.get("predictions", [])}:
        raise ValueError("Module context must cover the frozen slate")
    scenarios = {str(row["game_id"]): row for row in injury_adjustment.get("games", [])}
    if set(scenarios) != {str(row["game_id"]) for row in snapshot.get("predictions", [])}:
        raise ValueError("Injury scenarios must cover the frozen slate")
    actuals = player_rows(boxscores)
    settled_ids = None
    if isinstance(settled, dict):
        settled_ids = {str(row.get("game_id")) for row in settled.get("games", [])}
    games = []
    for fixture in snapshot.get("predictions", []):
        gid = str(fixture["game_id"])
        actual_for_game = {pid: row for (game_id, pid), row in actuals.items() if game_id == gid}
        if settled_ids is not None and gid not in settled_ids:
            continue
        if not actual_for_game:
            continue
        scenario = scenarios[gid]
        context = module_context.get("games", {}).get(gid, {})
        claims = claims_by_team(context)
        starters = lineup_starters(context)
        teams = {}
        for team in (fixture["home_team"], fixture["away_team"]):
            team_scenario = _team_scenario(scenario, team)
            accepted = team_scenario.get("accepted_out_players", [])
            predicted_out = {str(row.get("player_id")): row for row in accepted if row.get("player_id")}
            allocation = team_scenario.get("minute_redistribution") or {}
            changes = {str(row.get("player_id")): row for row in allocation.get("changes", []) if row.get("player_id")}
            team_claims = claims.get(team, {})
            team_actuals = {pid: row for pid, row in actual_for_game.items() if row.get("team") == team}
            ids = set(team_claims) | set(predicted_out) | set(changes) | set(team_actuals)
            audits = []
            for pid in sorted(ids):
                claim = team_claims.get(pid)
                out_item = predicted_out.get(pid)
                change = changes.get(pid)
                actual = team_actuals.get(pid)
                name = (claim or {}).get("player") or (out_item or {}).get("player") or (change or {}).get("player")
                audits.append(_player_audit(pid, name, claim, out_item, change, actual))
            team_starters = starters.get(team, {})
            actual_starters = sorted(row.get("player") for row in team_actuals.values()
                                      if row.get("starter_reported_postgame") is True and row.get("player"))
            projected_starters = [
                row.get("player") if isinstance(row, dict) else row
                for row in team_starters.get("players", [])
            ]
            teams[team] = {
                "scenario_status": team_scenario.get("status"),
                "scenario_reason": team_scenario.get("reason"),
                "accepted_out_players": accepted,
                "unresolved_out_claims": team_scenario.get("unresolved_out_claims", []),
                "minute_redistribution_status": allocation.get("status"),
                "projected_lineup_status": team_starters.get("status"),
                "projected_starters": projected_starters,
                "actual_starters": actual_starters,
                "player_audits": audits,
                "actual_participation_rows": len(team_actuals),
                "actual_points": sum(row.get("points") or 0 for row in team_actuals.values()),
                "actual_rebounds": sum(row.get("rebounds") or 0 for row in team_actuals.values()),
                "actual_assists": sum(row.get("assists") or 0 for row in team_actuals.values()),
            }
        games.append({
            "game_id": gid,
            "home_team": fixture["home_team"],
            "away_team": fixture["away_team"],
            "tipoff_utc": fixture["tipoff_utc"],
            "pregame_prediction_as_of_utc": snapshot["created_at_utc"],
            "baseline_home_probability": fixture.get("hybrid_p_home"),
            "injury_scenario_status": scenario.get("status"),
            "injury_scenario_reason": scenario.get("reason"),
            "injury_adjusted_home_probability": scenario.get("injury_adjusted_home_probability"),
            "home_probability_delta_pp": scenario.get("home_probability_delta_pp"),
            "calibrated": False,
            "production_approved": False,
            "teams": teams,
        })
    settled_at = (settled or {}).get("created_at_utc") if isinstance(settled, dict) else None
    return {
        "schema_version": 1,
        "kind": "nba_injury_replacement_postmortem_v1",
        "snapshot_sha256": snapshot_sha,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settled_at_utc": settled_at,
        "games": games,
        "postgame_data_used": True,
        "model_probabilities_modified": False,
        "causal_injury_effect_claimed": False,
        "limitations": [
            "Actual participation and minutes are observations, not proof of causal injury impact.",
            "Minutes comparisons can differ due overtime, game flow, foul trouble, and coaching decisions.",
            "Pregame claims and projected replacement minutes remain frozen to their original source timestamp.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--injury", required=True)
    parser.add_argument("--module-context", required=True)
    parser.add_argument("--boxscores", required=True)
    parser.add_argument("--settled")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    documents = [json.loads(Path(path).read_text()) for path in (
        args.snapshot, args.injury, args.module_context, args.boxscores
    )]
    settled = json.loads(Path(args.settled).read_text()) if args.settled else None
    report = build(*documents, settled=settled)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
    summary = {
        "completed_games_audited": len(report["games"]),
        "games_with_experimental_injury_probability": sum(
            row.get("injury_scenario_status") == "research_scenario" for row in report["games"]
        ),
        "model_probabilities_modified": False,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
