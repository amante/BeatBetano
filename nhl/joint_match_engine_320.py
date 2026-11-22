"""One traceable NHL goal process from a dated matchup input bundle.

This is a transparent research engine, not a fitted/calibrated predictor. It
uses the projected skaters' observed production and deployment, team shot
prevention, the PP/PK matchup, observed penalty-minute rates, and separate
scenarios for every unconfirmed goalie candidate. It fails closed for
publication when identity/source requirements are incomplete.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from nhl.goal_process import calculate


VERSION = "nhl-joint-match-320-v10"


def _num(value, label, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing or invalid " + label)
    if value < 0 or (positive and value <= 0):
        raise ValueError("Out-of-range " + label)
    return float(value)


def _derived_assists(points, goals, label):
    if points + 1e-8 < goals:
        raise ValueError(label + " points below goal credits")
    return max(0.0, points - goals)


def _time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _player_rate(player, field):
    gp = _num(player.get("games_played"), "player games", positive=True)
    return _num(player.get("production", {}).get(field), "player " + field) / gp


def _minutes_scenario(team):
    """Allocate 180 forward and 120 defense skater-minutes to projected players."""
    players = [p for line in team["projected_lines"] for p in line["players"]]
    changes = team.get("lineup_changes", {})
    outgoing = list(changes.get("out_of_projection", []))
    outgoing_by_id = {p.get("player_id") for p in outgoing}
    for player in team.get("unavailable_players", []):
        pid = player.get("player_id")
        active_ids = {p.get("player_id") for p in players}
        if pid is not None and pid not in active_ids and pid not in outgoing_by_id and player.get("production"):
            outgoing.append(player)
            outgoing_by_id.add(pid)
    incoming = changes.get("new_in_projection", [])
    by_id = {p["player_id"]: p for p in players}

    def total_minutes(player):
        return sum(_num(x, "change player minutes") for x in player["minutes_per_game"].values())

    incoming_ids = {p["player_id"] for p in incoming}
    if not incoming_ids.issubset(by_id):
        raise ValueError("An incoming player is absent from the projected 18")
    result = {}
    group_audit = {}
    partial = bool(team.get("lineup_coverage", {}).get("partial"))
    for group, full_target in (("forwards", 180.0), ("defense", 120.0)):
        members = [p for line in team["projected_lines"] if line["unit"] == group for p in line["players"]]
        expected_count = 12 if group == "forwards" else 6
        target = full_target * len(members) / expected_count if partial else full_target
        group_incoming = [p for p in members if p["player_id"] in incoming_ids]
        group_retained = [p for p in members if p["player_id"] not in incoming_ids]
        entry = sum(total_minutes(p) for p in group_incoming)
        historical_reference = sum(total_minutes(p) for p in members)
        entry_factor = min(1.0, target / entry) if entry else 1.0
        remaining = target - entry * entry_factor
        retained_budget = sum(total_minutes(p) for p in group_retained)
        if remaining > 0 and retained_budget <= 0:
            raise ValueError("Cannot allocate remaining minutes to retained " + group)
        for player in members:
            old = total_minutes(player)
            new = old * entry_factor if player["player_id"] in incoming_ids else (remaining * old / retained_budget if retained_budget else 0.0)
            shares = {key: player["minutes_per_game"][key] / old for key in ("EV", "PP", "PK")}
            result[player["player_id"]] = {"total": new, "EV": new * shares["EV"],
                                           "PP": new * shares["PP"], "PK": new * shares["PK"]}
        group_outgoing = [p for p in outgoing if (p.get("position") == "D") == (group == "defense")]
        group_audit[group] = {"target_minutes": target,"full_target_minutes": full_target,
                              "unresolved_reserved_minutes": full_target-target,"modeled_player_count": len(members),
                              "outgoing_minutes": sum(total_minutes(p) for p in group_outgoing),
                              "incoming_historical_minutes": entry,
                              "projected_historical_reference_minutes": historical_reference,
                              "allocated_minutes": sum(result[p["player_id"]]["total"] for p in members)}
    baseline_budget = sum(v["target_minutes"] for v in group_audit.values())
    full_reference_budget = 300.0
    historical_reference = sum(v["projected_historical_reference_minutes"] for v in group_audit.values())
    lost = sum(v["outgoing_minutes"] for v in group_audit.values())
    entry = sum(v["incoming_historical_minutes"] for v in group_audit.values())
    if not math.isclose(sum(x["total"] for x in result.values()), baseline_budget, abs_tol=1e-8):
        raise ValueError("Projected minute distribution does not conserve the team budget")
    return result, {"outgoing_minutes": lost, "incoming_historical_minutes": entry,
                   "historical_reference_minutes": historical_reference,"reference_minutes": baseline_budget,
                   "full_reference_minutes": full_reference_budget,
                   "unresolved_reserved_minutes": full_reference_budget-baseline_budget,"partial_projection": partial,
                   "allocated_minutes": sum(x["total"] for x in result.values()),
                   "incoming_player_ids": sorted(incoming_ids), "by_group": group_audit}


def _apply_return_minutes(team, minute_scenario, minute_audit):
    """Apply evidence-gated return ramp, redistributing minutes inside the same unit."""
    records = team.get("return_to_play", {}).get("players", {})
    if not isinstance(records, dict):
        records = {}
    players = {p["player_id"]: p for line in team.get("projected_lines", [])
               for p in line.get("players", [])}
    audit_rows = []
    applied = {}
    for key, item in records.items():
        if not isinstance(item, dict):
            continue
        try:
            player_id = int(item.get("player_id", key))
        except (TypeError, ValueError):
            continue
        player = players.get(player_id)
        if player is None:
            continue
        status = item.get("status", "evidence_unavailable")
        row = {"player_id": player_id, "name": item.get("name") or player.get("name"),
               "status": status, "days_out": item.get("days_out"),
               "duration_band": item.get("duration_band"),
               "historical_players": item.get("historical_players", 0),
               "historical_episodes": item.get("historical_episodes", 0),
               "minutes_factor": 1.0, "minutes_before": minute_scenario[player_id]["total"],
               "minutes_after": minute_scenario[player_id]["total"]}
        if status == "adjustment_applied":
            factor = item.get("minutes_factor")
            if type(factor) not in (int, float) or not math.isfinite(factor) or not 0.70 <= factor < 0.995:
                row["status"] = "invalid_adjustment_ignored"
            else:
                row["minutes_factor"] = float(factor)
                applied[player_id] = (row, float(factor))
        audit_rows.append(row)
    if not applied:
        result = {"status": "no_supported_adjustment", "applied": False, "players": audit_rows}
        minute_audit["return_to_play"] = result
        return minute_scenario, minute_audit

    by_player = {row["player_id"]: row for row in audit_rows}
    successful = set()
    for group in ("forwards", "defense"):
        members = [p for line in team.get("projected_lines", []) if line.get("unit") == group
                   for p in line.get("players", [])]
        returners = [p for p in members if p["player_id"] in applied]
        recipients = [p for p in members if p["player_id"] not in applied]
        recipient_minutes = sum(minute_scenario[p["player_id"]]["total"] for p in recipients)
        reductions = sum(minute_scenario[p["player_id"]]["total"] * (1.0 - applied[p["player_id"]][1])
                         for p in returners)
        if not returners or recipient_minutes <= 0:
            for player in returners:
                by_player[player["player_id"]]["status"] = "minutes_reallocation_unavailable"
                by_player[player["player_id"]]["minutes_factor"] = 1.0
            continue
        for player in returners:
            pid = player["player_id"]
            minutes = minute_scenario[pid]
            _, factor = applied[pid]
            for key in ("total", "EV", "PP", "PK"):
                minutes[key] *= factor
            by_player[pid]["minutes_after"] = minutes["total"]
            successful.add(pid)
        if reductions:
            for player in recipients:
                pid = player["player_id"]
                minutes = minute_scenario[pid]
                before = minutes["total"]
                addition = reductions * before / recipient_minutes
                shares = {key: minutes[key] / before for key in ("EV", "PP", "PK")} if before > 0 else {"EV": 0, "PP": 0, "PK": 0}
                minutes["total"] = before + addition
                for key in ("EV", "PP", "PK"):
                    minutes[key] += addition * shares[key]
    if not successful:
        minute_audit["return_to_play"] = {"status": "minutes_reallocation_unavailable",
                                          "applied": False, "players": audit_rows}
        return minute_scenario, minute_audit
    allocated = sum(item["total"] for item in minute_scenario.values())
    if not math.isclose(allocated, minute_audit["allocated_minutes"], abs_tol=1e-7):
        raise ValueError("Return-to-play minute redistribution does not conserve the team budget")
    for group, detail in minute_audit.get("by_group", {}).items():
        group_ids = {p["player_id"] for line in team["projected_lines"] if line.get("unit") == group
                     for p in line.get("players", [])}
        detail["allocated_minutes"] = sum(minute_scenario[pid]["total"] for pid in group_ids)
    result = {"status": "adjustment_applied", "applied": True, "players": audit_rows,
              "method": "scale returning skater minutes and redistribute within same forward/defense unit"}
    minute_audit["return_to_play"] = result
    return minute_scenario, minute_audit


def _historical_contribution(player):
    gp = _num(player.get("games_played"), "availability player games", positive=True)
    prod = player.get("production", {})
    minutes = player.get("minutes_per_game", {})
    return {
        "minutes": sum(_num(minutes.get(key), "availability minutes") for key in ("EV", "PP", "PK")),
        "goals": sum(_num(prod.get(key), "availability goals") for key in ("evGoals", "ppGoals", "shGoals")) / gp,
        "assists": _num(prod.get("assists"), "availability assists") / gp,
        "shots": _num(prod.get("shots"), "availability shots") / gp,
        "pim": _num(prod.get("penaltyMinutes"), "availability PIM") / gp,
    }


def _partial_roster_ledger(team, skaters, full_totals, team_games):
    """Keep unidentified roster production at its aggregate baseline; adjust only identified players."""
    active_ids={p["player_id"] for p in skaters}; unavailable={}
    candidates=list(team.get("unavailable_players",[]))+list(team.get("lineup_changes",{}).get("out_of_projection",[]))
    for p in candidates:
        pid=p.get("player_id")
        if pid is not None and pid not in active_ids and p.get("production"): unavailable[pid]=p
    fields=("evGoals","ppGoals","shGoals","evPoints","ppPoints","shPoints","assists","shots","penaltyMinutes")
    base,residual,absent={},{},{}
    for field in fields:
        base[field]=_num(full_totals.get(field),"team roster "+field)/team_games
        known=sum(_num(p.get("production",{}).get(field),"identified skater "+field) for p in skaters)/team_games
        removed=sum(_num(p.get("production",{}).get(field),"reported absence "+field) for p in unavailable.values())/team_games
        remaining=base[field]-known-removed
        if remaining < -0.02: raise ValueError("Partial lineup contribution exceeds team roster baseline for "+field)
        residual[field]=max(0.0,remaining);absent[field]=removed
    base["goals"]=base["evGoals"]+base["ppGoals"]+base["shGoals"]
    residual["goals"]=residual["evGoals"]+residual["ppGoals"]+residual["shGoals"]
    absent["goals"]=absent["evGoals"]+absent["ppGoals"]+absent["shGoals"]
    return {"base":base,"residual":residual,"absent":absent,"excluded_player_ids":sorted(unavailable)}


def _apply_rotowire_power_play(team, minute_scenario, skaters, minute_audit):
    """Reallocate the existing PP-minute budget to a fully resolved RotoWire PP1/PP2."""
    def skip(reason):
        minute_audit["rotowire_power_play"] = {
            "status": "not_applied", "applied": False, "reason": reason,
            "probability_delta": None,
        }
        return minute_scenario, minute_audit

    evidence = team.get("rotowire_pregame")
    if not isinstance(evidence, dict) or evidence.get("status") != "observed":
        return skip("rotowire_observation_unavailable")
    units = {}
    for key in ("power_play_1", "power_play_2"):
        item = evidence.get(key)
        if not isinstance(item, dict) or item.get("status") != "observed":
            return skip(key + "_not_observed")
        people = item.get("players")
        if not isinstance(people, list) or len(people) != 5:
            return skip(key + "_does_not_have_five_resolved_players")
        ids = []
        for person in people:
            pid = person.get("player_id") if isinstance(person, dict) else None
            if type(pid) is not int or pid <= 0:
                return skip(key + "_contains_unresolved_player_identity")
            ids.append(pid)
        if len(set(ids)) != 5:
            return skip(key + "_contains_duplicate_player_identity")
        units[key] = ids
    if set(units["power_play_1"]) & set(units["power_play_2"]):
        return skip("player_appears_in_both_power_play_units")

    roster_by_id = {player["player_id"]: player for player in skaters}
    pp_ids = set(units["power_play_1"] + units["power_play_2"])
    missing = sorted(pp_ids - set(roster_by_id))
    if missing:
        return skip("power_play_player_not_in_projected_roster:" + ",".join(map(str, missing)))

    pp_budget = sum(row["PP"] for row in minute_scenario.values())
    if pp_budget <= 1e-9:
        return skip("no_projected_team_power_play_minutes")
    capacities = {
        pid: max(0.0, minute_scenario[pid]["total"] - minute_scenario[pid]["PK"])
        for pid in pp_ids
    }
    if sum(capacities.values()) + 1e-8 < pp_budget:
        return skip("projected_power_play_budget_exceeds_unit_capacity")
    weights = {
        pid: _num(roster_by_id[pid].get("minutes_per_game", {}).get("PP"),
                  "historical PP minutes for RotoWire player")
        for pid in pp_ids
    }
    if sum(weights.values()) <= 1e-9:
        return skip("no_historical_PP_minutes_for_RotoWire_units")

    allocation = {pid: 0.0 for pid in pp_ids}
    remaining = pp_budget
    available = set(pp_ids)
    while remaining > 1e-8 and available:
        weight_total = sum(weights[pid] for pid in available)
        if weight_total <= 1e-9:
            return skip("historical_PP_minutes_cannot_allocate_full_budget")
        capped = []
        for pid in available:
            proposed = remaining * weights[pid] / weight_total
            room = capacities[pid] - allocation[pid]
            if proposed > room + 1e-8:
                capped.append(pid)
        if not capped:
            for pid in available:
                allocation[pid] += remaining * weights[pid] / weight_total
            remaining = 0.0
            break
        for pid in capped:
            room = max(0.0, capacities[pid] - allocation[pid])
            allocation[pid] += room
            remaining -= room
            available.remove(pid)
    if remaining > 1e-6:
        return skip("could_not_conserve_projected_power_play_minutes")

    prior_pp_goals = 0.0
    revised_pp_goals = 0.0
    for player in skaters:
        pid = player["player_id"]
        row = minute_scenario[pid]
        prior_pp = row["PP"]
        target_pp = allocation.get(pid, 0.0)
        gp = _num(player.get("games_played"), "RotoWire player games", positive=True)
        historical_pp = _num(player.get("minutes_per_game", {}).get("PP"), "historical player PP minutes") * gp
        pp_goals = _num(player.get("production", {}).get("ppGoals"), "historical player PP goals")
        rate = pp_goals / historical_pp if historical_pp > 0 else 0.0
        prior_pp_goals += rate * prior_pp
        revised_pp_goals += rate * target_pp
        if target_pp:
            row["EV"] = row["total"] - row["PK"] - target_pp
            if row["EV"] < -1e-8:
                return skip("power_play_minutes_would_make_EV_minutes_negative")
            row["PP"] = target_pp
        else:
            row["EV"] += prior_pp
            row["PP"] = 0.0

    minute_audit["rotowire_power_play"] = {
        "status": "applied", "applied": True,
        "source_role": "projected_provider_units_not_official_confirmation",
        "method": "preserve_team_PP_minutes_and_reallocate_by_prior_player_PP_TOI_within_projected_PP1_PP2",
        "team_PP_minutes_before": pp_budget,
        "team_PP_minutes_after": sum(row["PP"] for row in minute_scenario.values()),
        "projected_PP_goals_before": prior_pp_goals,
        "projected_PP_goals_after": revised_pp_goals,
        "projected_PP_goal_delta": revised_pp_goals - prior_pp_goals,
        "units": {
            "PP1": [{"player_id": pid, "name": roster_by_id[pid]["name"],
                     "historical_PP_minutes_per_game": weights[pid],
                     "projected_PP_minutes": allocation[pid]} for pid in units["power_play_1"]],
            "PP2": [{"player_id": pid, "name": roster_by_id[pid]["name"],
                     "historical_PP_minutes_per_game": weights[pid],
                     "projected_PP_minutes": allocation[pid]} for pid in units["power_play_2"]],
        },
        "probability_delta": None,
        "calibrated": False,
    }
    if not math.isclose(sum(row["PP"] for row in minute_scenario.values()), pp_budget, abs_tol=1e-7):
        raise ValueError("RotoWire PP redistribution does not conserve team PP minutes")
    if not math.isclose(sum(row["total"] for row in minute_scenario.values()),
                        minute_audit["allocated_minutes"], abs_tol=1e-7):
        raise ValueError("RotoWire PP redistribution does not conserve skater minutes")
    return minute_scenario, minute_audit


def _rotowire_aggregate_pp_adjustment(team):
    """Use only fully identified RotoWire PP1/PP2 in the team-aggregate fallback."""
    def skipped(reason):
        return {"applied": False, "reason": reason}

    evidence = team.get("rotowire_pregame") or {}
    if evidence.get("status") != "observed" or evidence.get("capture_status") != "captured":
        return skipped("rotowire_observation_unavailable")
    units = {}
    for key in ("power_play_1", "power_play_2"):
        section = evidence.get(key) or {}
        if section.get("status") != "observed":
            return skipped(key + "_not_observed")
        rows = section.get("players")
        if not isinstance(rows, list) or len(rows) != 5:
            return skipped(key + "_does_not_have_five_resolved_players")
        if any(type(row.get("player_id")) is not int for row in rows):
            return skipped(key + "_contains_unresolved_player_identity")
        units[key] = rows
    ids = [row["player_id"] for rows in units.values() for row in rows]
    if len(set(ids)) != 10:
        return skipped("player_appears_in_both_power_play_units")

    roster_rows = team.get("team_roster_skaters") or []
    roster = {}
    for row in roster_rows:
        pid = row.get("player_id")
        if type(pid) is not int or pid in roster:
            return skipped("aggregate_roster_identity_invalid")
        roster[pid] = row
    if not roster:
        return skipped("aggregate_roster_history_unavailable")
    missing = [str(pid) for pid in ids if pid not in roster]
    if missing:
        return skipped("power_play_player_not_in_team_roster:" + ",".join(missing))

    confirmed_out = set()
    uncertain = set()
    injury_section = evidence.get("injuries") or {}
    for row in injury_section.get("players", []) if isinstance(injury_section, dict) else []:
        pid = row.get("player_id")
        status = str(row.get("reported_status") or "").upper()
        if type(pid) is int and status in {"OUT", "IR", "IR-LT", "IR-NR"}:
            confirmed_out.add(pid)
        elif type(pid) is int and status in {"DTD", "DAY-TO-DAY", "QUESTIONABLE", "LIKELY"}:
            uncertain.add(pid)
    if set(ids) & confirmed_out:
        return skipped("power_play_unit_conflicts_with_reported_unavailable_player")
    if set(ids) & uncertain:
        return skipped("power_play_unit_has_uncertain_availability")

    team_games = _num(team.get("team_summary", {}).get("gamesPlayed"), "team games", positive=True)
    total_pp_minutes = 0.0
    historical_pp_goals = 0.0
    unit_pp_minutes = {}
    unit_pp_goals = {}
    for pid, row in roster.items():
        gp = _num(row.get("games_played"), "roster player games", positive=True)
        minutes = _num(row.get("minutes_per_game", {}).get("PP"), "roster player PP minutes")
        goals = _num(row.get("production", {}).get("ppGoals"), "roster player PP goals")
        historical_minutes = minutes * gp
        total_pp_minutes += historical_minutes
        historical_pp_goals += goals
        if pid in ids:
            unit_pp_minutes[pid] = historical_minutes
            unit_pp_goals[pid] = goals
    unit_minutes_total = sum(unit_pp_minutes.values())
    if total_pp_minutes <= 0 or unit_minutes_total <= 0:
        return skipped("no_historical_PP_minutes_for_RotoWire_units")

    pp_budget = total_pp_minutes / team_games
    projected_goals = 0.0
    projected_minutes = {}
    for pid in ids:
        allocation = pp_budget * unit_pp_minutes[pid] / unit_minutes_total
        projected_minutes[pid] = allocation
        rate = unit_pp_goals[pid] / unit_pp_minutes[pid] if unit_pp_minutes[pid] else 0.0
        projected_goals += rate * allocation
    baseline_goals = historical_pp_goals / team_games
    delta = projected_goals - baseline_goals
    if not all(math.isfinite(value) for value in (pp_budget, projected_goals, baseline_goals, delta)):
        return skipped("invalid_aggregate_PP_projection")

    return {
        "applied": True,
        "method": "reallocate_observed_team_PP_skater_minutes_to_exact_RotoWire_PP1_PP2_by_historical_PP_TOI",
        "team_PP_minutes_before": pp_budget,
        "team_PP_minutes_after": sum(projected_minutes.values()),
        "projected_PP_goals_before": baseline_goals,
        "projected_PP_goals_after": projected_goals,
        "projected_PP_goal_delta": delta,
        "units": {
            key.replace("power_play_", "PP"): [
                {"player_id": row["player_id"],
                 "name": row.get("resolved_name") or row.get("name"),
                 "historical_PP_minutes_per_game": (
                     unit_pp_minutes[row["player_id"]] /
                     _num(roster[row["player_id"]].get("games_played"), "PP player games", positive=True)
                 ),
                 "projected_PP_minutes": projected_minutes[row["player_id"]]}
                for row in rows
            ]
            for key, rows in units.items()
        },
        "confirmed_unavailable_players": [
            {"player_id": row.get("player_id"),
             "name": row.get("resolved_name") or row.get("name"),
             "status": row.get("reported_status")}
            for row in injury_section.get("players", [])
            if isinstance(injury_section, dict) and isinstance(row, dict)
            and row.get("player_id") in confirmed_out
        ],
        "official": False,
        "calibrated": False,
    }


def team_profile(team, team_code):
    summary = team["team_summary"]
    st = team["special_teams"]
    roster = team["projected_lines"]
    skaters = [p for line in roster for p in line["players"]]
    coverage = team.get("lineup_coverage", {})
    partial_lineup = bool(coverage.get("partial"))
    if len({p.get("player_id") for p in skaters}) != len(skaters) or len(skaters) > 18:
        raise ValueError("Duplicate or excessive projected identities for " + team_code)
    if not partial_lineup and len(skaters) != 18:
        raise ValueError("Expected 12 forwards and 6 defensemen for " + team_code)
    if partial_lineup and not skaters and coverage.get("mode") != "team_aggregate_fallback":
        raise ValueError("No identified projected skaters for partial scenario " + team_code)

    if coverage.get("mode") == "team_aggregate_fallback":
        gp = _num(summary.get("gamesPlayed"), "team games", positive=True)
        rotowire_pp_adjustment = _rotowire_aggregate_pp_adjustment(team)
        shots_for = _num(summary.get("shotsForPerGame"), "team shots for", positive=True)
        shots_against = _num(summary.get("shotsAgainstPerGame"), "team shots against", positive=True)
        goals_for = _num(summary.get("goalsForPerGame"), "team goals for", positive=True)
        goals_against = _num(summary.get("goalsAgainstPerGame"), "team goals against", positive=True)
        goalies = team.get("goalie_candidates", [])
        if not goalies:
            raise ValueError("No team or goalie baseline for " + team_code)
        rates = {"ev_goals": 0.0, "pp_goals": 0.0, "sh_goals": 0.0,
                 "ev_points": 0.0, "pp_points": 0.0, "sh_points": 0.0,
                 "ev_assists": 0.0, "pp_assists": 0.0, "sh_assists": 0.0,
                 "assists": 0.0, "shots": 0.0, "ev_shots": 0.0,
                 "pim": 0.0, "ev_minutes": 0.0, "pp_minutes": 0.0,
                 "pk_minutes": 0.0}
        return {
            "team": team_code, "summary": summary, "players": [],
            "lineup_coverage": coverage, "rates": rates,
            "credit_ratios": {"EV": None, "PP": None, "PK": None},
            "goal_event_rates_from_player_goals": {"EV": 0.0, "PP": 0.0, "PK": 0.0},
            "historical_assists_per_goal": None,
            "season": {"games": gp, "shots_for_per_game": shots_for,
                       "shots_against_per_game": shots_against,
                       "goals_for_per_game": goals_for,
                       "goals_against_per_game": goals_against},
            "special": {"games": 0, "pp_per_game": 0.0, "pp_goal_rate": None,
                        "pk_opportunities_per_game": 0.0, "pk_goals_allowed_rate": None,
                        "pp_goals_per_game": 0.0},
            "team_pim_per_game": None, "projected_pim_per_game": 0.0,
            "penalty_rate_ratio": None, "projected_pp_goals_per_game": 0.0,
            "projected_pp_minutes_per_game": 0.0,
            "faceoff_win_pct": summary.get("faceoffWinPct"), "ev_share": 0.0,
            "goalies": goalies, "schedule": team.get("schedule", {}),
            "minute_distribution": {"status": "omitted_team_aggregate_fallback",
                                    "rotowire_power_play": rotowire_pp_adjustment},
            "rotowire_pp_adjustment": rotowire_pp_adjustment,
            "player_contributions": [],
            "lineup_impact": {"status": "omitted_team_aggregate_fallback"},
        }

    minute_scenario, minute_audit = _minutes_scenario(team)
    minute_scenario, minute_audit = _apply_return_minutes(team, minute_scenario, minute_audit)
    minute_scenario, minute_audit = _apply_rotowire_power_play(team, minute_scenario, skaters, minute_audit)
    rates = {"ev_goals": 0.0, "pp_goals": 0.0, "sh_goals": 0.0,
             "ev_points": 0.0, "pp_points": 0.0, "sh_points": 0.0,
             "ev_assists": 0.0, "pp_assists": 0.0, "sh_assists": 0.0,
             "assists": 0.0, "shots": 0.0, "ev_shots": 0.0,
             "pim": 0.0, "ev_minutes": 0.0, "pp_minutes": 0.0,
             "pk_minutes": 0.0}
    player_contributions = []
    for player in skaters:
        if player.get("availability") != "active":
            raise ValueError("Unavailable player present in projected lines")
        if player.get("team_abbrevs") != team_code:
            raise ValueError("Projected skater identity does not match " + team_code)
        prod = player.get("production")
        minutes = player.get("minutes_per_game")
        total_toi = _num(player.get("total_minutes_per_game"), "total player TOI", positive=True)
        gp = _num(player.get("games_played"), "player games", positive=True)
        ev = _num(minutes.get("EV"), "EV minutes")
        pp = _num(minutes.get("PP"), "PP minutes")
        pk = _num(minutes.get("PK"), "PK minutes")
        if ev + pp + pk > total_toi + 1.5:
            raise ValueError("Situation TOI exceeds total TOI for " + player["name"])
        goals = _num(prod.get("goals"), "goals")
        ev_goals = _num(prod.get("evGoals"), "EV goals")
        pp_goals = _num(prod.get("ppGoals"), "PP goals")
        sh_goals = _num(prod.get("shGoals"), "shorthanded goals")
        ev_points = _num(prod.get("evPoints"), "EV points")
        pp_points = _num(prod.get("ppPoints"), "PP points")
        sh_points = _num(prod.get("shPoints"), "shorthanded points")
        ev_assists = _derived_assists(ev_points, ev_goals, "EV")
        pp_assists = _derived_assists(pp_points, pp_goals, "PP")
        sh_assists = _derived_assists(sh_points, sh_goals, "SH")
        shots = _num(prod.get("shots"), "shots")
        scenario = minute_scenario[player["player_id"]]
        historical_ev_total = ev * gp
        historical_pp_total = pp * gp
        historical_pk_total = pk * gp
        historical_total_toi = total_toi * gp
        ev_rate = _num(prod.get("evGoals"), "EV goals") / historical_ev_total if historical_ev_total else 0
        pp_rate = pp_goals / historical_pp_total if historical_pp_total else 0
        sh_rate = sh_goals / historical_pk_total if historical_pk_total else 0
        total_shots_rate = shots / historical_total_toi if historical_total_toi else 0
        ev_assist_rate = ev_assists / historical_ev_total if historical_ev_total else 0
        pp_assist_rate = pp_assists / historical_pp_total if historical_pp_total else 0
        sh_assist_rate = sh_assists / historical_pk_total if historical_pk_total else 0
        total_pim_rate = _num(prod.get("penaltyMinutes"), "penalty minutes") / historical_total_toi if historical_total_toi else 0
        rates["ev_goals"] += ev_rate * scenario["EV"]
        rates["pp_goals"] += pp_rate * scenario["PP"]
        rates["sh_goals"] += sh_rate * scenario["PK"]
        rates["ev_points"] += ev_points / historical_ev_total * scenario["EV"] if historical_ev_total else 0
        rates["pp_points"] += pp_points / historical_pp_total * scenario["PP"] if historical_pp_total else 0
        rates["sh_points"] += sh_points / historical_pk_total * scenario["PK"] if historical_pk_total else 0
        rates["ev_assists"] += ev_assist_rate * scenario["EV"]
        rates["pp_assists"] += pp_assist_rate * scenario["PP"]
        rates["sh_assists"] += sh_assist_rate * scenario["PK"]
        rates["assists"] += (ev_assist_rate * scenario["EV"] +
                             pp_assist_rate * scenario["PP"] +
                             sh_assist_rate * scenario["PK"])
        rates["shots"] += total_shots_rate * scenario["total"]
        rates["ev_shots"] += total_shots_rate * scenario["EV"]
        rates["pim"] += total_pim_rate * scenario["total"]
        rates["ev_minutes"] += scenario["EV"]
        rates["pp_minutes"] += scenario["PP"]
        rates["pk_minutes"] += scenario["PK"]
        baseline = {"minutes": total_toi, "EV": ev, "PP": pp, "PK": pk,
                    "goals": (_num(prod.get("evGoals"), "EV goals") + pp_goals + sh_goals) / gp,
                    "assists": _num(prod.get("assists"), "assists") / gp,
                    "shots": shots / gp,
                    "pim": _num(prod.get("penaltyMinutes"), "penalty minutes") / gp}
        projected_ev_assists = ev_assist_rate * scenario["EV"]
        projected_pp_assists = pp_assist_rate * scenario["PP"]
        projected_sh_assists = sh_assist_rate * scenario["PK"]
        projected = {"minutes": scenario["total"], "EV": scenario["EV"],
                     "PP": scenario["PP"], "PK": scenario["PK"],
                     "EV_goals": ev_rate * scenario["EV"],
                     "PP_goals": pp_rate * scenario["PP"],
                     "SH_goals": sh_rate * scenario["PK"],
                     "goals": ev_rate * scenario["EV"] + pp_rate * scenario["PP"] + sh_rate * scenario["PK"],
                     "EV_assists": projected_ev_assists,
                     "PP_assists": projected_pp_assists,
                     "SH_assists": projected_sh_assists,
                     "assists": projected_ev_assists + projected_pp_assists + projected_sh_assists,
                     "shots": total_shots_rate * scenario["total"],
                     "pim": total_pim_rate * scenario["total"]}
        line = next(line for line in roster if player in line["players"])
        player_contributions.append({"player_id": player["player_id"], "name": player["name"],
                                     "unit": line["unit"], "line": line["line"],
                                     "baseline": baseline, "projected": projected,
                                     "delta": {key: projected[key] - baseline[key] for key in baseline}})

    for group, count in (("forwards", 12), ("defense", 6)):
        actual=sum(len(line["players"]) for line in roster if line["unit"]==group)
        if (not partial_lineup and actual!=count) or (partial_lineup and actual>count):
            raise ValueError("Invalid projected line structure for "+team_code)

    gp = _num(summary.get("gamesPlayed"), "team games", positive=True)
    pp_opp = _num(st.get("powerplay_opportunities"), "PP opportunities")
    pp_for = _num(st.get("powerplay_goals"), "PP goals")
    sh_opp = _num(st.get("times_shorthanded"), "times shorthanded")
    pk_against = _num(st.get("opponent_powerplay_goals"), "PP goals allowed")
    st_gp = _num(st.get("games_played"), "special teams games", positive=True)
    shots_for = _num(summary.get("shotsForPerGame"), "team shots for", positive=True)
    shots_against = _num(summary.get("shotsAgainstPerGame"), "team shots against", positive=True)
    pim_total = _num(team["team_roster_penalty_minutes"].get("total"), "team penalty minutes")
    pim_gp = _num(team["team_roster_penalty_minutes"].get("games_played"), "team PIM games", positive=True)
    if team["team_roster_penalty_minutes"].get("unattributed_multi_team_players"):
        raise ValueError("Team PIM baseline has multi-team player records")
    goalie_candidates = team.get("goalie_candidates", [])
    if not goalie_candidates:
        raise ValueError("No goalie scenarios for " + team_code)

    team_pim_per_game = pim_total / pim_gp
    if team_pim_per_game <= 0:
        raise ValueError("No team penalty-minute reference for " + team_code)
    full_roster = team.get("team_roster_production", {})
    if full_roster.get("unattributed_multi_team_players"):
        raise ValueError("Cannot attribute current team production after player trades")
    full_totals = full_roster.get("totals", {})
    partial_ledger=None
    if partial_lineup:
        team_games=_num(summary.get("gamesPlayed"),"team games",positive=True)
        partial_ledger=_partial_roster_ledger(team,skaters,full_totals,team_games)
        for rate_key,stat_key in (("ev_goals","evGoals"),("pp_goals","ppGoals"),("sh_goals","shGoals"),
            ("ev_points","evPoints"),("pp_points","ppPoints"),("sh_points","shPoints"),
            ("shots","shots"),("pim","penaltyMinutes")):
            rates[rate_key]+=partial_ledger["residual"][stat_key]
        residual=partial_ledger["residual"]
        residual_assists = 0.0
        for phase,points_key,goals_key in (("ev","evPoints","evGoals"),("pp","ppPoints","ppGoals"),("sh","shPoints","shGoals")):
            phase_residual = _derived_assists(residual[points_key],residual[goals_key],"Residual "+phase.upper())
            rates[phase+"_assists"] += phase_residual
            residual_assists += phase_residual
        rates["assists"] += residual_assists
        modeled=rates["ev_minutes"]+rates["pp_minutes"]+rates["pk_minutes"]
        reserved=minute_audit["unresolved_reserved_minutes"]
        if modeled>0 and reserved>0:
            shares={key:rates[key+"_minutes"]/modeled for key in ("ev","pp","pk")}
            rates["ev_minutes"]+=reserved*shares["ev"]
            rates["pp_minutes"]+=reserved*shares["pp"]
            rates["pk_minutes"]+=reserved*shares["pk"]
            rates["ev_shots"]+=partial_ledger["residual"]["shots"]*shares["ev"]
    credit_ratios = {}
    for strength, goals_key, points_key in (("EV", "evGoals", "evPoints"),
                                             ("PP", "ppGoals", "ppPoints"),
                                             ("PK", "shGoals", "shPoints")):
        goals = _num(full_totals.get(goals_key), "roster " + strength + " goals")
        points = _num(full_totals.get(points_key), "roster " + strength + " points")
        credit_ratios[strength] = points / goals if goals else None
    # Goals drive the team score. Assists estimate a player's own G+A point
    # distribution; counting them again as team goals double-counts scoring.
    event_rates = {"EV": rates["ev_goals"], "PP": rates["pp_goals"], "PK": rates["sh_goals"]}
    total_roster_goals = sum(_num(full_totals.get(key), "roster goals") for key in ("evGoals", "ppGoals", "shGoals"))
    assist_goal_ratio = (_num(full_totals.get("assists"), "roster assists") / total_roster_goals
                         if total_roster_goals > 0 else None)
    active_ids={p["player_id"] for p in skaters}
    change_data=team.get("lineup_changes",{});incoming=list(change_data.get("new_in_projection",[]))
    incoming_ids={p.get("player_id") for p in incoming};outgoing=list(change_data.get("out_of_projection",[]))
    outgoing_by_id={p.get("player_id"):p for p in outgoing if p.get("player_id") is not None}
    for player in team.get("unavailable_players",[]):
        pid=player.get("player_id")
        if pid is not None and pid not in active_ids and pid not in outgoing_by_id and player.get("production"):
            outgoing.append(player);outgoing_by_id[pid]=player
    if partial_lineup:
        aggregate,residual=partial_ledger["base"],partial_ledger["residual"]
        baseline_totals={"minutes":300.0,"goals":aggregate["goals"],"assists":aggregate["assists"],
                         "shots":aggregate["shots"],"pim":aggregate["penaltyMinutes"]}
        known={k:sum(x["projected"][k] for x in player_contributions) for k in ("minutes","goals","assists","shots","pim")}
        projected_totals={"minutes":300.0,"goals":residual["goals"]+known["goals"],
                          "assists":residual["assists"]+known["assists"],"shots":residual["shots"]+known["shots"],
                          "pim":residual["penaltyMinutes"]+known["pim"]}
    else:
        prior_ids={p["player_id"] for p in skaters if p["player_id"] not in incoming_ids}
        baseline_totals={key:0.0 for key in ("minutes","goals","assists","shots","pim")}
        baseline_group_totals={group:{key:0.0 for key in baseline_totals} for group in ("forwards","defense")}
        for player in outgoing:
            contribution=_historical_contribution(player);group="defense" if player.get("position")=="D" else "forwards"
            for key in baseline_totals: baseline_totals[key]+=contribution[key];baseline_group_totals[group][key]+=contribution[key]
        for player in skaters:
            if player["player_id"] in prior_ids:
                item=next(item for item in player_contributions if item["player_id"]==player["player_id"])
                contribution=item["baseline"];group=item["unit"]
                for key in baseline_totals: baseline_totals[key]+=contribution[key];baseline_group_totals[group][key]+=contribution[key]
        for group,target in (("forwards",180.0),("defense",120.0)):
            reference=baseline_group_totals[group]["minutes"];scale=target/reference if reference>0 else 0.0
            for key in ("goals","assists","shots","pim"): baseline_group_totals[group][key]*=scale
            baseline_group_totals[group]["minutes"]=target
        for key in baseline_totals: baseline_totals[key]=sum(baseline_group_totals[group][key] for group in baseline_group_totals)
        projected_totals={key:sum(item["projected"][key] for item in player_contributions) for key in baseline_totals}
    outgoing_totals={key:0.0 for key in ("minutes","goals","assists","shots","pim")}
    for player in outgoing:
        if player.get("production") and player.get("games_played"):
            values=_historical_contribution(player)
            for key in outgoing_totals: outgoing_totals[key]+=values[key]
    incoming_totals={key:0.0 for key in ("minutes","goals","assists","shots","pim")}
    for item in player_contributions:
        if item["player_id"] in incoming_ids:
            for key in incoming_totals: incoming_totals[key]+=item["projected"][key]
    lineup_impact={
        "out_of_projection":[{"player_id":p.get("player_id"),"name":p.get("name"),
            "contribution_per_game":_historical_contribution(p)} for p in outgoing if p.get("production") and p.get("games_played")],
        "out_of_projection_total_per_game":outgoing_totals,
        "incoming_total_after_reallocation_per_game":incoming_totals,
        "incoming_to_projected_lineup":[{"player_id":item["player_id"],"name":item["name"],
            "projected_contribution_per_game":item["projected"],
            "minute_and_production_delta_vs_historical_usage":item["delta"]}
            for item in player_contributions if item["player_id"] in incoming_ids],
        "team_net_change_vs_previous_roster_per_game":{key:projected_totals[key]-baseline_totals[key] for key in baseline_totals},
        "projected_lineup_totals_per_game":projected_totals,"reference_lineup_totals_per_game":baseline_totals,
        "partial_projection":partial_lineup,"identity_coverage":coverage if partial_lineup else None,
        "unresolved_roster_residual_per_game":residual if partial_lineup else None,
    }
    pp_minutes = rates["pp_minutes"]
    projected_pp_goals = rates["pp_goals"]
    active_pim_ratio = rates["pim"] / team_pim_per_game
    # Opportunities come from both sides of the matchup. The roster PIM ratio
    # scales opponent penalties; it is an empirical exposure proxy, not a rule
    # that equates every PIM minute to one power play.
    ev_share = rates["ev_minutes"] / max(1e-12, rates["ev_minutes"] + pp_minutes + rates["pk_minutes"])
    return {
        "team": team_code,
        "summary": summary,
        "players": skaters,
        "lineup_coverage": coverage,
        "rates": rates,
        "credit_ratios": credit_ratios,
        "goal_event_rates_from_player_goals": event_rates,
        "historical_assists_per_goal": assist_goal_ratio,
        "season": {"games": gp, "shots_for_per_game": shots_for,
                   "shots_against_per_game": shots_against,
                   "goals_for_per_game": _num(summary.get("goalsForPerGame"), "team goals for"),
                   "goals_against_per_game": _num(summary.get("goalsAgainstPerGame"), "team goals against")},
        "special": {"games": st_gp, "pp_per_game": pp_opp / st_gp,
                    "pp_goal_rate": pp_for / pp_opp if pp_opp else None,
                    "pk_opportunities_per_game": sh_opp / st_gp,
                    "pk_goals_allowed_rate": pk_against / sh_opp if sh_opp else None,
                    "pp_goals_per_game": pp_for / st_gp},
        "team_pim_per_game": team_pim_per_game,
        "projected_pim_per_game": rates["pim"],
        "penalty_rate_ratio": active_pim_ratio,
        "projected_pp_goals_per_game": projected_pp_goals,
        "projected_pp_minutes_per_game": pp_minutes,
        "faceoff_win_pct": _num(summary.get("faceoffWinPct"), "team faceoff rate"),
        "ev_share": ev_share,
        "goalies": goalie_candidates,
        "schedule": team.get("schedule", {}),
        "minute_distribution": minute_audit,
        "player_contributions": player_contributions,
        "lineup_impact": lineup_impact,
    }


def _goalie_scenarios(team):
    candidates = []
    for goalie in team["goalies"]:
        if goalie.get("status") != "observed":
            continue
        sv = goalie.get("metrics", {}).get("season_to_date", {})
        shots = _num(sv.get("shots_against"), "goalie shots against", positive=True)
        saves = _num(sv.get("saves"), "goalie saves")
        if saves > shots:
            raise ValueError("Goalie saves exceed shots against")
        probability=goalie.get("starter_probability")
        if probability is not None:
            probability=_num(probability,"goalie starter probability")
            if probability>1: raise ValueError("Goalie starter probability exceeds one")
        candidates.append({"id": goalie.get("player_id"), "name": goalie.get("name"),
                           "save_pct": saves / shots, "shots_faced": shots,
                           "source_status": goalie.get("candidate_status"),
                           "starter_confirmed": bool(goalie.get("independently_confirmed_starter")),
                           "starter_probability": probability})
    if not candidates:
        raise ValueError("No observed goalie rates")
    return candidates


def _scoring_rate(attacking, defending, goalie, league_pk_rate):
    """Expected goals in regulation from lineup rates and opponent conditions."""
    ar, dr = attacking["rates"], defending["rates"]
    # Player shots are weighted by their observed even-strength share. The
    # opponent's season shot-prevention rate supplies the defensive matchup.
    ev_shots_for = ar["ev_shots"]
    ev_shots_against = defending["season"]["shots_against_per_game"] * attacking["ev_share"]
    expected_ev_shots = math.sqrt(max(1e-9, ev_shots_for * ev_shots_against))
    shot_factor = expected_ev_shots / max(1e-9, ev_shots_for)
    non_pp_rate = attacking["goal_event_rates_from_player_goals"]["EV"] * shot_factor

    # Estimate penalty opportunities from both clubs' dated special-team
    # counts. Active opponent PIM exposure adjusts opportunities empirically.
    own_pp = attacking["special"]["pp_per_game"]
    opp_pk_opps = defending["special"]["pk_opportunities_per_game"]
    expected_pp_opps = (own_pp + opp_pk_opps) / 2 * defending["penalty_rate_ratio"]
    own_pp_rate = attacking["special"]["pp_goal_rate"]
    opp_pk_leak = defending["special"]["pk_goals_allowed_rate"]
    if own_pp_rate is None or opp_pk_leak is None or league_pk_rate <= 0:
        raise ValueError("Incomplete PP/PK rates")
    pp_lineup_goals = attacking["goal_event_rates_from_player_goals"]["PP"] * expected_pp_opps / max(1e-9, own_pp)
    pp_lineup_rate = pp_lineup_goals / max(1e-9, expected_pp_opps)
    # Match own team efficiency, the projected PP personnel, and opponent PK
    # allowance. Shrink the short opponent PK sample halfway toward the
    # games-weighted league rate; this is explicit, not a fitted coefficient.
    pk_rate_shrunk = math.sqrt(max(1e-12, opp_pk_leak * league_pk_rate))
    pp_rate = expected_pp_opps * (max(1e-12, own_pp_rate * pp_lineup_rate * pk_rate_shrunk) ** (1 / 3))
    pp_matchup_factor = pp_rate / max(1e-9, expected_pp_opps * own_pp_rate)
    short_handed_rate = ar["sh_goals"]

    # Replace the opponent's historical aggregate save effect with each
    # candidate goalkeeper's own season-to-date save rate.
    opponent_baseline_goal_rate = (defending["season"]["goals_against_per_game"] /
                                   defending["season"]["shots_against_per_game"])
    if opponent_baseline_goal_rate <= 0:
        raise ValueError("Invalid team defensive goal-per-shot rate")
    goalie_goal_rate = 1 - goalie["save_pct"]
    goalie_factor = goalie_goal_rate / opponent_baseline_goal_rate
    expected_ev_goals = non_pp_rate * goalie_factor
    expected_pp_goals = pp_rate * goalie_factor
    expected_sh_goals = short_handed_rate * goalie_factor
    rate = expected_ev_goals + expected_pp_goals + expected_sh_goals
    if not math.isfinite(rate) or rate <= 0 or rate >= 10:
        raise ValueError("Unsupported expected goal rate")
    return {
        "expected_goals": rate,
        "expected_goals_by_strength": {"EV": expected_ev_goals, "PP": expected_pp_goals,
                                       "SH": expected_sh_goals},
        "components": {
            "projected_ev_goals_per_game": ar["ev_goals"],
            "projected_ev_scoring_events_from_player_goals": attacking["goal_event_rates_from_player_goals"]["EV"],
            "ev_points_per_goal_credit_ratio": attacking["credit_ratios"]["EV"],
            "projected_ev_shots_per_game": ar["ev_shots"],
            "opponent_ev_shots_allowed_proxy": ev_shots_against,
            "expected_ev_shots": expected_ev_shots,
            "ev_shot_matchup_factor": shot_factor,
            "projected_pp_goals_per_game": ar["pp_goals"],
            "projected_pp_scoring_events_from_player_goals": attacking["goal_event_rates_from_player_goals"]["PP"],
            "pp_points_per_goal_credit_ratio": attacking["credit_ratios"]["PP"],
            "expected_pp_opportunities": expected_pp_opps,
            "team_pp_goal_rate": own_pp_rate,
            "projected_pp_line_goal_rate": pp_lineup_rate,
            "opponent_pk_goals_allowed_rate": opp_pk_leak,
            "league_pk_goals_allowed_rate": league_pk_rate,
            "opponent_pk_rate_after_league_shrinkage": pk_rate_shrunk,
            "opponent_pk_matchup_factor": pp_matchup_factor,
            "projected_short_handed_goals_per_game": short_handed_rate,
            "opponent_goalie_save_pct": goalie["save_pct"],
            "goalie_matchup_factor": goalie_factor,
            "lineup_assists_per_game_context": ar["assists"],
            "lineup_pim_per_game": ar["pim"],
            "opponent_lineup_pim_ratio": defending["penalty_rate_ratio"],
            "ev_minutes_per_game": ar["ev_minutes"],
            "pp_minutes_per_game": ar["pp_minutes"],
            "pk_minutes_per_game": ar["pk_minutes"],
        },
    }



def _aggregate_scoring_rate(attacking, defending, goalie):
    """Conservative team-season fallback when a projected lineup is unavailable."""
    attack = attacking["season"]["goals_for_per_game"]
    allow = defending["season"]["goals_against_per_game"]
    shots_against = defending["season"]["shots_against_per_game"]
    if attack <= 0 or allow <= 0 or shots_against <= 0:
        raise ValueError("Invalid official team aggregate rates for fallback")
    baseline_goal_rate = allow / shots_against
    if baseline_goal_rate <= 0:
        raise ValueError("Invalid opponent team goal-per-shot baseline")
    save_pct = _num(goalie.get("save_pct"), "goalie save percentage")
    if save_pct >= 1:
        raise ValueError("Invalid goalie save percentage")
    goalie_factor = (1 - save_pct) / baseline_goal_rate
    pp_adjustment = attacking.get("rotowire_pp_adjustment") or {}
    pp_delta = (pp_adjustment.get("projected_PP_goal_delta", 0.0)
                if pp_adjustment.get("applied") is True else 0.0)
    aggregate_rate = math.sqrt(attack * allow) + pp_delta
    if not math.isfinite(aggregate_rate) or aggregate_rate <= 0:
        raise ValueError("RotoWire PP adjustment yields an invalid aggregate goal rate")
    expected = aggregate_rate * goalie_factor
    if not math.isfinite(expected) or expected <= 0 or expected >= 10:
        raise ValueError("Unsupported aggregate fallback goal rate")
    return {
        "expected_goals": expected,
        "expected_goals_by_strength": None,
        "components": {
            "forecast_basis": "official_team_season_goal_rates_and_goalie_scenario",
            "attacking_goals_for_per_game": attack,
            "opponent_goals_against_per_game": allow,
            "team_aggregate_baseline": math.sqrt(attack * allow),
            "rotowire_PP1_PP2_adjustment": pp_adjustment,
            "aggregate_baseline_PP_goal_delta": pp_delta,
            "opponent_goalie_save_pct": save_pct,
            "opponent_goalie_factor": goalie_factor,
            "individual_lineup_adjustment": "omitted_projected_lineup_unavailable",
            "special_teams_personnel_adjustment": "omitted_projected_lineup_unavailable",
        },
    }


def _apply_division_rivalry(home_scoring, away_scoring, evidence):
    """Apply a bounded prior-history goal-differential shift before market math."""
    requested = 0.0
    if isinstance(evidence, dict) and evidence.get("status") in ("applied", "eligible_no_directional_signal"):
        candidate = evidence.get("expected_goal_differential_delta", 0.0)
        if type(candidate) not in (int, float) or not math.isfinite(candidate) or abs(candidate) > 0.35:
            raise ValueError("Invalid division/rivalry adjustment")
        requested = float(candidate)
    old_home = home_scoring["expected_goals"]
    old_away = away_scoring["expected_goals"]
    applied = max(-2 * (old_home - 0.05), min(2 * (old_away - 0.05), requested))
    for scoring, delta in ((home_scoring, applied / 2), (away_scoring, -applied / 2)):
        old = scoring["expected_goals"]
        new = old + delta
        if old <= 0 or new <= 0:
            raise ValueError("Division/rivalry shift produced invalid expected goals")
        factor = new / old
        by_strength=scoring.get("expected_goals_by_strength")
        scoring["expected_goals_by_strength"] = ({
            strength: value * factor for strength,value in by_strength.items()
        } if isinstance(by_strength,dict) else None)
        scoring["expected_goals"] = new
        scoring["components"]["division_rivalry_goal_rate_factor"] = factor
    output = dict(evidence or {})
    output.update({
        "requested_goal_differential_delta": requested,
        "applied_goal_differential_delta": applied,
        "home_expected_goals_delta": applied / 2,
        "away_expected_goals_delta": -applied / 2,
        "applied_to_percentages": abs(applied) > 1e-9,
        "calibrated": False,
    })
    return output


def _poisson_probability_at_least_one(mean):
    return -math.expm1(-mean)


def _player_probabilities(team, scoring):
    """Allocate game-scoring means to skaters, then derive experimental G/A/P props."""
    phase_rates = {"EV": team["rates"]["ev_goals"],
                   "PP": team["rates"]["pp_goals"],
                   "SH": team["rates"]["sh_goals"]}
    phase_means = scoring["expected_goals_by_strength"]
    team_assists_by_strength = {}
    for phase, credit_key in (("EV","EV"),("PP","PP"),("SH","PK")):
        ratio = team["credit_ratios"][credit_key]
        team_assists_by_strength[phase] = (
            phase_means[phase] * max(0.0, ratio - 1.0) if ratio is not None else 0.0
        )
    rows = []
    for item in team["player_contributions"]:
        projected = item["projected"]
        goal_mean = 0.0
        for phase in ("EV", "PP", "SH"):
            denominator = phase_rates[phase]
            if denominator > 0:
                goal_mean += phase_means[phase] * projected[phase + "_goals"] / denominator
        assists_by_strength = {}
        for phase in ("EV","PP","SH"):
            denominator = team["rates"][phase.lower()+"_assists"]
            player_assists_in_phase = projected[phase+"_assists"]
            assists_by_strength[phase] = (
                team_assists_by_strength[phase] * player_assists_in_phase / denominator
                if denominator > 0 else 0.0
            )
        player_assists = sum(assists_by_strength.values())
        point_mean = goal_mean + player_assists
        probability = {
            "goal_at_least_one": _poisson_probability_at_least_one(goal_mean),
            "assist_at_least_one": (_poisson_probability_at_least_one(player_assists)
                                    if player_assists is not None else None),
            "point_at_least_one": (_poisson_probability_at_least_one(point_mean)
                                   if point_mean is not None else None),
            "point_two_or_more": (max(0.0, 1.0 - math.exp(-point_mean) * (1.0 + point_mean))
                                  if point_mean is not None else None),
        }
        rows.append({
            "player_id": item["player_id"], "name": item["name"],
            "unit": item["unit"], "line": item["line"],
            "status": "experimental_probability",
            "expected": {"goals": goal_mean, "assists": player_assists,
                         "assists_by_strength": assists_by_strength, "points": point_mean},
            "probability": probability,
            "points_identity": "expected_points = expected_goals + expected_assists",
            "probability_model": "independent Poisson player goal and assist counts; assists allocated by EV/PP/SH-specific historical credits and projected deployment",
        })
    return rows


def run(inputs):
    if inputs.get("kind") != "nhl_joint_match_inputs_v1":
        raise ValueError("Unsupported joint-match input kind")
    home_code, away_code = inputs.get("home"), inputs.get("away")
    if not home_code or not away_code or home_code == away_code:
        raise ValueError("Invalid home/away identity")
    start = _time(inputs["start_utc"])
    captured = _time(inputs["captured_at_utc"])
    cutoff = inputs.get("cutoff_exclusive")
    if not cutoff or cutoff >= start.date().isoformat():
        raise ValueError("Input date cutoff is not strictly before the game")
    original_team_inputs = inputs["teams"]
    aggregate_fallback = any(
        original_team_inputs[code].get("lineup_coverage", {}).get("mode") == "team_aggregate_fallback"
        for code in (home_code, away_code)
    )
    # Keep source-attested RotoWire PP units available in aggregate mode.
    # The aggregate profile applies only a separate PP personnel delta; it does
    # not infer 5v5 lines or promote a partial roster to a confirmed lineup.
    profile_inputs = original_team_inputs
    home = team_profile(profile_inputs[home_code], home_code)
    away = team_profile(profile_inputs[away_code], away_code)
    league_pk_rate = _num(inputs["league_context"].get("powerplay_goals_allowed_per_opportunity"),
                          "league PK rate", positive=True)
    unknowns = list(inputs.get("unknowns", []))
    rotowire_pp_applied = any(
        profile.get("minute_distribution", {}).get("rotowire_power_play", {}).get("applied") is True
        for profile in (home, away)
    )
    base_home = base_away = None
    if rotowire_pp_applied:
        home_without_rotowire = dict(inputs["teams"][home_code], rotowire_pregame=None)
        away_without_rotowire = dict(inputs["teams"][away_code], rotowire_pregame=None)
        base_home = team_profile(home_without_rotowire, home_code)
        base_away = team_profile(away_without_rotowire, away_code)
    for team in (home, away):
        for player in inputs["teams"][team["team"]].get("unavailable_players", []):
            if player.get("availability") == "injury" and player.get("player_id") is None:
                unknowns.append(team["team"] + " injury identity unresolved: " + player["name"])
            elif player.get("production") is None:
                unknowns.append(team["team"] + " missing prior history for " + player["name"])
    scenarios = []
    home_goalies, away_goalies = _goalie_scenarios(home), _goalie_scenarios(away)
    for hg in home_goalies:
        for ag in away_goalies:
            rate = _aggregate_scoring_rate if aggregate_fallback else None
            h = rate(home, away, ag) if rate else _scoring_rate(home, away, ag, league_pk_rate)
            a = rate(away, home, hg) if rate else _scoring_rate(away, home, hg, league_pk_rate)
            division_rivalry = _apply_division_rivalry(h, a, inputs.get("division_rivalry"))
            markets = calculate(h["expected_goals"], a["expected_goals"])
            pp_impact = None
            if rotowire_pp_applied:
                base_rate = _aggregate_scoring_rate if aggregate_fallback else None
                base_h = base_rate(base_home, base_away, ag) if base_rate else _scoring_rate(base_home, base_away, ag, league_pk_rate)
                base_a = base_rate(base_away, base_home, hg) if base_rate else _scoring_rate(base_away, base_home, hg, league_pk_rate)
                base_markets = calculate(base_h["expected_goals"], base_a["expected_goals"])

                def difference(after, before):
                    if isinstance(after, dict) and isinstance(before, dict):
                        return {key: difference(value, before[key]) for key, value in after.items()
                                if key in before}
                    if type(after) in (int, float) and type(before) in (int, float):
                        return after - before
                    return None

                pp_impact = {
                    "status": "applied_unvalidated_scenario_delta",
                    "home_expected_goals_without_PP1_PP2": base_h["expected_goals"],
                    "away_expected_goals_without_PP1_PP2": base_a["expected_goals"],
                    "current_home_expected_goals": h["expected_goals"],
                    "current_away_expected_goals": a["expected_goals"],
                    "markets_without_PP1_PP2": base_markets,
                    "market_probability_delta": difference(markets, base_markets),
                    "official": False,
                    "calibrated": False,
                }
            home_player_probabilities = [] if aggregate_fallback else _player_probabilities(home, h)
            away_player_probabilities = [] if aggregate_fallback else _player_probabilities(away, a)
            weight=(hg["starter_probability"]*ag["starter_probability"]
                    if hg["starter_probability"] is not None and ag["starter_probability"] is not None else None)
            scenarios.append({"home_goalie": hg, "away_goalie": ag, "scenario_weight": weight,
                              "expected_goals": {"home": h["expected_goals"], "away": a["expected_goals"],
                                                 "total": h["expected_goals"] + a["expected_goals"]},
                              "expected_goals_by_strength": (
                                  {home_code: h["expected_goals_by_strength"],
                                   away_code: a["expected_goals_by_strength"]}
                                  if h["expected_goals_by_strength"] is not None
                                  and a["expected_goals_by_strength"] is not None else None),
                              "rotowire_pp_impact": pp_impact,
                              "forecast_basis": "team_aggregate_fallback" if aggregate_fallback else "projected_skaters_and_goalie_scenarios",
                              "division_rivalry": division_rivalry,
                              "home_components": h["components"], "away_components": a["components"],
                              "player_probabilities": {home_code: home_player_probabilities,
                                                       away_code: away_player_probabilities},
                              "markets": markets})
    weighted_summary=None
    if scenarios and all(s["scenario_weight"] is not None for s in scenarios):
        weight_total=sum(s["scenario_weight"] for s in scenarios)
        if math.isclose(weight_total,1.0,abs_tol=1e-8):
            market_keys=("regulation","illustrative_ml","three_goal_lead","first_to_three_goal_lead","comeback_after_two_goal_deficit","strong_win_regulation","double_chance_regulation")
            weighted_markets={}
            for key in market_keys:
                outcomes=scenarios[0]["markets"][key]
                weighted_markets[key]={name:sum(s["scenario_weight"]*s["markets"][key][name] for s in scenarios)
                                       for name in outcomes}
            weighted_summary={
                "status":"empirically_weighted_scenarios",
                "method":"independent home/away candidate starter shares from season-to-date gamesStarted divided by team games played",
                "scenario_weight_sum":weight_total,
                "expected_goals":{"home":sum(s["scenario_weight"]*s["expected_goals"]["home"] for s in scenarios),
                                  "away":sum(s["scenario_weight"]*s["expected_goals"]["away"] for s in scenarios),
                                  "total":sum(s["scenario_weight"]*s["expected_goals"]["total"] for s in scenarios)},
                "expected_goals_by_strength":{
                    team:{strength:sum(s["scenario_weight"]*s["expected_goals_by_strength"][team][strength]
                                       for s in scenarios)
                          for strength in ("EV","PP","SH")}
                    for team in (home_code,away_code)
                } if all(isinstance(s.get("expected_goals_by_strength"),dict)
                         and all(isinstance(s["expected_goals_by_strength"].get(team),dict)
                                 for team in (home_code,away_code)) for s in scenarios) else None,
                "markets":weighted_markets,
                "calibrated":False,"official":False}
    reconstruction = bool(inputs.get("poststart_reconstruction")) or captured >= start
    return {
        "kind": "nhl_joint_match_scenarios_v1",
        "model_version": VERSION,
        "game_id": inputs["game_id"],
        "home": home_code,
        "away": away_code,
        "start_utc": inputs["start_utc"],
        "forecast_basis": "team_aggregate_fallback" if aggregate_fallback else "projected_skaters_and_goalie_scenarios",
        "lineup_fallback": {
            "applied": aggregate_fallback,
            "player_props_available": not aggregate_fallback,
            "reason": "At least one team has no identified projected skaters; team-season goal rates and goalie scenarios used for both teams." if aggregate_fallback else None,
            "omitted_factors": (["projected 5v5 lines", "player-level props", "5v5 absence and replacement effects"] +
                                ([] if rotowire_pp_applied else ["RotoWire PP1/PP2 deployment"])) if aggregate_fallback else [],
        },
        "source_cutoff_exclusive": cutoff,
        "captured_at_utc": inputs["captured_at_utc"],
        "status": "historical_reconstruction_only" if reconstruction else "conditional_unvalidated_scenarios",
        "publishable": False,
        "scenario_count": len(scenarios),
        "goalie_start_distribution": {home_code: inputs["teams"][home_code].get("goalie_start_distribution"),
                                      away_code: inputs["teams"][away_code].get("goalie_start_distribution")},
        "rotowire_pregame": {
            "status": "observed" if any((inputs["teams"][code].get("rotowire_pregame") or {}).get("status") == "observed" for code in (home_code, away_code)) else "unavailable",
            "teams": {code: inputs["teams"][code].get("rotowire_pregame") for code in (home_code, away_code)},
            "market_observation": inputs["teams"][home_code].get("rotowire_market_observation"),
            "source": inputs["teams"][home_code].get("rotowire_source") or inputs["teams"][away_code].get("rotowire_source"),
            "probabilities_modified": rotowire_pp_applied,
            "power_play_adjustment_applied": rotowire_pp_applied,
        },
        "scenario_weighted_summary": weighted_summary,
        "scenarios": scenarios,
        "minute_distribution": {home_code: home["minute_distribution"],
                                away_code: away["minute_distribution"]},
        "lineup_coverage": {home_code: home["lineup_coverage"], away_code: away["lineup_coverage"]},
        "lineup_impact": (
            {home_code: {"status": "not_applied_missing_projected_lineup"},
             away_code: {"status": "not_applied_missing_projected_lineup"}}
            if aggregate_fallback else
            {home_code: home["lineup_impact"], away_code: away["lineup_impact"]}
        ),
        "player_contributions": {home_code: [] if aggregate_fallback else home["player_contributions"],
                                 away_code: [] if aggregate_fallback else away["player_contributions"]},
        "player_scoring_model": {
            "team_score_influence": "player goal rates by EV/PP/SH deployment feed team expected goals and game outcome probabilities",
            "assists_role": "individual assists are distributed by EV/PP/SH historical points-minus-goals rates and projected minutes; assists contribute to individual points but not extra team goals",
            "point_identity": "points = goals + assists",
            "player_probabilities_vary_by_goalie_scenario": not aggregate_fallback,
            "status": "omitted_projected_lineup_unavailable" if aggregate_fallback else "experimental_player_rates",
            "calibrated": False,
        },
        "schedule_context": {home_code: {"context": home["schedule"], "probability_effect_applied": False},
                             away_code: {"context": away["schedule"], "probability_effect_applied": False}},
        "possession_context": {home_code: {"faceoff_win_pct": home["faceoff_win_pct"],
                                            "probability_effect": "embedded in observed shot and scoring rates"},
                               away_code: {"faceoff_win_pct": away["faceoff_win_pct"],
                                            "probability_effect": "embedded in observed shot and scoring rates"}},
        "unresolved": sorted(set(unknowns)),
        "calibrated": False,
        "official": False,
        "odds_used": False,
        "limitations": [
            "Poisson rates use observed per-game player production and shot rates, not fitted coefficients.",
            "Individual defender on-ice suppression and line-pair effects are unavailable; team shots-against is used.",
            "Projected trios/pairs identify personnel and deployment, but no line-chemistry or pair-specific matchup coefficient is estimated.",
            "Referee assignments do not change this goal projection; historical penalty-opportunity rates by assigned referee crew are not connected.",
            "Schedule, travel and back-to-back context have no estimated coefficient in the goal-rate calculation.",
            "For partial projected lineups, only identified skaters are minute-adjusted; unresolved roster contribution stays at its aggregate team baseline.",
            "If either team has no identified projected lineup, the matchup falls back symmetrically to official team-season goals-for/goals-against rates and goalie scenarios; no player props, lineup, injury-replacement, or PP-unit effects are issued for that matchup.",
            "Player-level anytime goal, assist, and point probabilities are exploratory independent-Poisson estimates and require walk-forward calibration.",
            "Player goals feed expected team goals by EV/PP/SH deployment. Assists are allocated by situation-specific historical player points-minus-goals per minute and projected deployment; PP1/PP2 reallocations therefore change individual assist and point shares without adding assists to team goals.",
            "Division/rivalry shifts expected goal differential using a bounded, shrunk split of strictly prior two-year regulation goal results; it is experimental, not calibrated, and is omitted when history is insufficient.",
            "Comeback probability means falling behind by at least two regulation goals and still winning the illustrative ML outcome; a regulation tie receives the same 50/50 overtime split as that market.",
            "PIM affects opportunity volume through an observed roster-to-team exposure ratio, not a fixed minutes-to-power-play conversion.",
            "Schedule, travel and back-to-back context are retained in source inputs but have no estimated coefficient.",
            "When candidate goalie starts exactly cover all prior team games, an experimental mix weights paired scenarios by each candidate's current-season gamesStarted share; this is an uncalibrated historical frequency, not a confirmed starter probability. Incomplete coverage leaves the mix unavailable.",
            "The engine must be wired to a fresh pregame capture before use in PULSO; this fixture was captured after puck drop.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(json.loads(Path(args.input).read_text()))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"game_id": result["game_id"], "scenarios": result["scenario_count"],
                      "status": result["status"], "publishable": result["publishable"]}))


if __name__ == "__main__":
    main()
