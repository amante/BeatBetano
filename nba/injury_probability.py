"""Experimental NBA win-probability sensitivity from exact official OUT claims.

This creates a side-by-side research scenario. It never overwrites the
statistical baseline or represents the adjustment as calibrated or approved.
"""
import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

MIN_MARGIN_HISTORY = 100
MAX_MARGIN_HISTORY = 1000
MAX_ABS_LOG_ODDS_DELTA = 0.75


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("Explicit UTC timestamp required")
    return parsed


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _verify_seal(document, field="content_sha256"):
    body = {key: value for key, value in document.items() if key != field}
    if document.get(field) != digest(body):
        raise ValueError("Input digest mismatch")


def _history_margins(history, cutoff):
    rows = history if isinstance(history, list) else history.get("games", [])
    margins = []
    for row in rows:
        try:
            tipoff = utc(row["tipoff_utc"])
            observed = utc(row.get("observed_at_utc", row["tipoff_utc"]))
            home, away = row["home_points"], row["away_points"]
        except (KeyError, TypeError, ValueError):
            continue
        if tipoff >= cutoff or observed > cutoff:
            continue
        if (type(home) not in (int, float) or type(away) not in (int, float)
                or not math.isfinite(home) or not math.isfinite(away)):
            continue
        margins.append((tipoff, float(home) - float(away)))
    margins.sort(key=lambda pair: pair[0])
    return [margin for _, margin in margins[-MAX_MARGIN_HISTORY:]]


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _team_points(team_data):
    if team_data.get("official_report_fixture_rows", 0) < 1:
        return None, "no_official_report_row_for_team"
    if team_data.get("roster_complete") is not True:
        return None, "incomplete_roster_identity"
    if team_data.get("conflicting_official_claims"):
        return None, "conflicting_official_statuses"
    out_count = team_data.get("official_out_count")
    if type(out_count) is not int or out_count < 0:
        return None, "invalid_official_out_count"
    losses = team_data.get("historical_output_loss_per_game") or {}
    gained = team_data.get("historical_output_from_added_minutes_per_game")
    if out_count == 0:
        if any(not _number(losses.get(field, 0)) for field in ("points",)):
            return None, "invalid_zero_out_baseline"
        return {"net_points_per_game": 0.0, "points_lost_per_game": 0.0,
                "points_added_per_game": 0.0, "official_out_count": 0,
                "out_players": []}, None
    allocation = team_data.get("minute_redistribution") or {}
    if allocation.get("status") != "conditional_historical_rotation_scenario":
        return None, "minute_redistribution_unavailable"
    if team_data.get("players_without_historical_minutes") or team_data.get("replacement_history_gaps"):
        return None, "incomplete_player_production_history"
    if not _number(losses.get("points")) or not isinstance(gained, dict) or not _number(gained.get("points")):
        return None, "missing_points_estimates"
    lost = float(losses["points"])
    added = float(gained["points"])
    if lost < 0 or added < 0:
        return None, "negative_points_estimate"
    out_players = [{"player": row.get("player"), "player_id": row.get("player_id"),
                    "status": row.get("official_status")}
                   for row in team_data.get("official_reported_players", [])
                   if row.get("official_status") == "out"]
    if len(out_players) != out_count:
        return None, "official_out_player_identity_mismatch"
    return {"net_points_per_game": added - lost, "points_lost_per_game": lost,
            "points_added_per_game": added, "official_out_count": out_count,
            "out_players": out_players}, None


def _eligible_out_claims(team_evidence):
    accepted = []
    unresolved = []
    for player in team_evidence if isinstance(team_evidence, list) else []:
        claims = player.get("claims", [])
        official_out = [claim for claim in claims
                        if claim.get("officially_verified") is True and claim.get("status") == "out"]
        if official_out:
            accepted.append({**player, "accepted_source_class": "official_nba_report",
                             "accepted_claims": official_out})
            continue
        if player.get("conflict"):
            if any(claim.get("status") == "out" for claim in claims):
                unresolved.append({"player_id": player.get("player_id"), "player": player.get("player"),
                                   "reason": "source_status_conflict"})
            continue
        provider_claims = [claim for claim in claims
                           if claim.get("source_type") == "provider_injury_report"
                           and claim.get("source") in ("CBS Sports", "ESPN")
                           and claim.get("status") == "out" and not claim.get("editorial_claim")]
        providers = {claim.get("source") for claim in provider_claims}
        if player.get("status_agreement") == "out" and len(providers) >= 2:
            source_class = "two_provider_consensus"
        elif player.get("status_agreement") == "out" and len(providers) == 1:
            source_class = "single_provider_research_claim"
        else:
            source_class = None
        if source_class:
            accepted.append({**player, "accepted_source_class": source_class,
                             "accepted_claims": provider_claims})
        elif any(claim.get("status") == "out" for claim in claims):
            unresolved.append({"player_id": player.get("player_id"), "player": player.get("player"),
                               "reason": "out_claim_lacks_trusted_provider_report"})
    return accepted, unresolved


def _eligible_uncertain_claims(team_evidence):
    accepted = []
    unresolved = []
    for player in team_evidence if isinstance(team_evidence, list) else []:
        claims = player.get("claims", [])
        uncertain = [claim for claim in claims if claim.get("status") in ("questionable", "doubtful")]
        if not uncertain:
            continue
        states = {claim.get("status") for claim in uncertain}
        if player.get("conflict") or len(states) != 1:
            unresolved.append({"player_id": player.get("player_id"), "player": player.get("player"),
                               "reason": "source_status_conflict"})
            continue
        state = next(iter(states))
        official = [claim for claim in uncertain if claim.get("officially_verified") is True]
        if official:
            accepted.append({**player, "scenario_status": state,
                             "accepted_source_class": "official_nba_report",
                             "accepted_claims": official})
            continue
        provider_claims = [claim for claim in uncertain
                           if claim.get("source_type") == "provider_injury_report"
                           and claim.get("source") in ("CBS Sports", "ESPN")
                           and not claim.get("editorial_claim")]
        providers = {claim.get("source") for claim in provider_claims}
        if player.get("status_agreement") == state and len(providers) >= 2:
            source_class = "two_provider_consensus"
        elif player.get("status_agreement") == state and len(providers) == 1:
            source_class = "single_provider_conditional_claim"
        else:
            source_class = None
        if source_class:
            accepted.append({**player, "scenario_status": state,
                             "accepted_source_class": source_class,
                             "accepted_claims": provider_claims})
        else:
            unresolved.append({"player_id": player.get("player_id"), "player": player.get("player"),
                               "status": state, "reason": "uncertain_status_lacks_trusted_provider_report"})
    return accepted, unresolved


def _uncertain_probability_range(fixture, teams_evidence, availability_game,
                                 rotation_game, lineup_game, player_rows,
                                 emitted, scale, unmatched_claims):
    import itertools
    from official_injury_impact import _history_by_player, _allocations, STAT_FIELDS

    uncertain = {}
    unresolved = []
    for team in (fixture["home_team"], fixture["away_team"]):
        rows, rejected = _eligible_uncertain_claims(teams_evidence.get(team, []))
        uncertain[team] = rows
        unresolved.extend({"team": team, **item} for item in rejected)
    unresolved.extend({"reason": "unmatched_uncertain_status", **claim}
                      for claim in unmatched_claims
                      if str(claim.get("status", "")).strip().casefold()
                      in ("questionable", "doubtful", "day to day"))
    count = sum(len(rows) for rows in uncertain.values())
    base = fixture["hybrid_p_home"]
    if not count:
        return {"status": "no_consensus_uncertain_status", "scenario_count": 0,
                "weights": None, "calibrated": False}
    if unresolved:
        return {"status": "incomplete_uncertain_evidence", "scenario_count": 0,
                "unresolved_claims": unresolved, "weights": None, "calibrated": False}
    if count > 4:
        return {"status": "too_many_uncertain_players", "scenario_count": 0,
                "uncertain_player_count": count, "maximum_supported": 4,
                "weights": None, "calibrated": False}
    if scale is None:
        return {"status": "blocked", "reason": "fewer_than_100_pre_emission_historical_margins",
                "scenario_count": 0, "weights": None, "calibrated": False}

    candidates = []
    for team, rows in uncertain.items():
        for item in rows:
            candidates.append({"team": team, "player_id": str(item.get("player_id")),
                               "player": item.get("player"), "status": item["scenario_status"],
                               "source_class": item["accepted_source_class"]})
    branches = []
    probabilities = []
    for choices in itertools.product(("available", "out"), repeat=count):
        assumed = {team: set() for team in uncertain}
        assumptions = []
        for item, choice in zip(candidates, choices):
            assumptions.append({**item, "assumption": choice})
            if choice == "out":
                assumed[item["team"]].add(item["player_id"])
        net = {}
        branch_error = None
        for team in (fixture["home_team"], fixture["away_team"]):
            impact, reason = _multi_source_team_points(
                team, availability_game.get(team, {}), rotation_game.get(team, {}),
                lineup_game.get(team, {}), player_rows, teams_evidence.get(team, []),
                emitted.isoformat(), fixture["tipoff_utc"], assumed[team])
            if reason == "no_secondary_provider_consensus_out" and not assumed[team]:
                net[team] = 0.0
            elif reason:
                branch_error = team + ":" + reason
                break
            else:
                net[team] = impact["estimated_net_points_per_game"]
        if branch_error:
            return {"status": "blocked", "reason": "incomplete_conditional_player_history_or_minutes:" + branch_error,
                    "scenario_count": len(branches), "weights": None, "calibrated": False}
        points_delta = net[fixture["home_team"]] - net[fixture["away_team"]]
        logit_delta = max(-MAX_ABS_LOG_ODDS_DELTA, min(MAX_ABS_LOG_ODDS_DELTA, points_delta / scale))
        baseline_logit = math.log(base / (1.0 - base))
        p_home = 1.0 / (1.0 + math.exp(-(baseline_logit + logit_delta)))
        branches.append({"assumptions": assumptions, "home_points_delta": points_delta,
                         "home_probability": p_home, "away_probability": 1.0 - p_home})
        probabilities.append(p_home)
    return {"status": "conditional_probability_range",
            "home_probability_min": min(probabilities), "home_probability_max": max(probabilities),
            "away_probability_min": 1.0 - max(probabilities), "away_probability_max": 1.0 - min(probabilities),
            "scenario_count": len(branches), "uncertain_player_count": count,
            "players": candidates, "branches": branches, "weights": None,
            "base_probability_used": base, "calibrated": False,
            "note": "Each branch treats every matched questionable/doubtful player as available or out. No probability weights are assigned."}

def _multi_source_team_points(team, availability_team, rotation_team, lineup_record,
                              player_rows, reconciled_players, emitted_at, tipoff, assumed_uncertain_ids=None):
    from official_injury_impact import _history_by_player, _allocations, STAT_FIELDS
    from starting_lineup_minutes import estimate as estimate_starter_minutes

    if availability_team.get("roster_complete") is not True:
        return None, "incomplete_current_roster"
    players = availability_team.get("players", [])
    by_id = {str(row.get("player_id")): row for row in players if row.get("player_id")}
    accepted, unresolved = _eligible_out_claims(reconciled_players)
    # Keep conflicting claims visible without suppressing other matched provider OUT rows.
    outs = []
    for item in accepted:
        pid = str(item.get("player_id"))
        if pid not in by_id:
            return {"unresolved_out_claims": [{"player_id": pid, "reason": "player_missing_from_current_roster"}]}, "player_missing_from_current_roster"
        outs.append({"player_id": pid, "player": by_id[pid].get("player"),
                     "accepted_source_class": item["accepted_source_class"],
                     "source_claims": item["accepted_claims"]})
    uncertain, _ = _eligible_uncertain_claims(reconciled_players)
    assumed_uncertain_ids = {str(pid) for pid in (assumed_uncertain_ids or set())}
    for item in uncertain:
        pid = str(item.get("player_id"))
        if pid in assumed_uncertain_ids:
            if pid not in by_id:
                return {"unresolved_out_claims": [{"player_id": pid, "reason": "player_missing_from_current_roster"}]}, "player_missing_from_current_roster"
            outs.append({"player_id": pid, "player": by_id[pid].get("player"),
                         "accepted_source_class": "conditional_uncertain_status",
                         "source_claims": item["accepted_claims"],
                         "reported_status": item["scenario_status"]})
    conditional_count = sum(row["accepted_source_class"] in (
        "conditional_uncertain_status", "single_provider_conditional_claim") for row in outs)
    secondary_count = sum(row["accepted_source_class"] == "two_provider_consensus" for row in outs)
    single_provider_count = sum(row["accepted_source_class"] == "single_provider_research_claim" for row in outs)
    provider_count = secondary_count + single_provider_count
    official_count = sum(row["accepted_source_class"] == "official_nba_report" for row in outs)
    if not provider_count and not official_count and not conditional_count:
        return {"official_out_count": 0, "secondary_consensus_out_count": 0,
                "secondary_provider_out_count": 0, "accepted_out_players": [],
                "unresolved_out_claims": unresolved}, "no_secondary_provider_consensus_out"

    samples = _history_by_player(player_rows, team, emitted_at, tipoff)
    out_ids = {row["player_id"] for row in outs}
    losses = {field: 0.0 for field in STAT_FIELDS}
    missing = []
    for row in outs:
        historical = samples.get(row["player_id"])
        if not historical or historical.get("average_minutes") is None:
            missing.append(row["player_id"] + ":minutes")
            continue
        for field in STAT_FIELDS:
            value = historical.get("per_game", {}).get(field)
            if value is None:
                missing.append(row["player_id"] + ":" + field)
            else:
                losses[field] += float(value)
    if missing:
        return {"accepted_out_players": outs, "players_without_historical_minutes": sorted(set(missing))}, "missing_out_player_history"

    starter_evidence = estimate_starter_minutes(team, availability_team, lineup_record or {},
                                                player_rows, emitted_at, tipoff)
    allocation = _allocations(team, rotation_team, out_ids, samples, outs, starter_evidence)
    if allocation.get("status") != "conditional_historical_rotation_scenario":
        return {"accepted_out_players": outs, "minute_redistribution": allocation}, "minute_redistribution_unavailable"
    added = {field: 0.0 for field in STAT_FIELDS}
    missing_recipients = []
    for change in allocation.get("changes", []):
        delta = change.get("minute_delta", 0)
        if delta <= 0:
            continue
        historical = samples.get(str(change.get("player_id")))
        if not historical or not historical.get("average_minutes"):
            missing_recipients.append(str(change.get("player_id")) + ":minutes")
            continue
        for field in STAT_FIELDS:
            value = historical.get("per_game", {}).get(field)
            if value is None:
                missing_recipients.append(str(change.get("player_id")) + ":" + field)
            else:
                added[field] += delta * float(value) / float(historical["average_minutes"])
    if missing_recipients:
        return {"accepted_out_players": outs, "minute_redistribution": allocation,
                "replacement_history_gaps": sorted(set(missing_recipients))}, "incomplete_replacement_history"
    return {"status": "conditional_historical_rotation_scenario",
            "official_out_count": official_count, "secondary_consensus_out_count": secondary_count,
            "secondary_provider_out_count": provider_count,
            "accepted_out_players": outs, "historical_output_loss_per_game": losses,
            "historical_output_from_added_minutes_per_game": added,
            "estimated_net_points_per_game": added["points"] - losses["points"],
            "minute_redistribution": allocation, "players_without_historical_minutes": [],
            "replacement_history_gaps": [], "source_agreement_rule": "NBA official OUT; otherwise a non-conflicting CBS Sports or ESPN provider OUT claim; two-provider agreement is retained when available",
            "conditional_uncertain_out_count": conditional_count,
            "unresolved_out_claims": unresolved}, None


def _multi_source_research_scenario(fixture, modules, history, player_history, emitted, margins, scale):
    from official_injury_impact import STAT_FIELDS
    gid = str(fixture["game_id"])
    evidence = modules.get("injury_source_reconciliation", {}).get("data", {})
    teams_evidence = evidence.get("teams", {})
    rotation_module = modules.get("rotation_minutes", {})
    availability_game = rotation_module.get("availability_status", {}).get("teams", {})
    rotation_game = rotation_module.get("historical_rotation", {}).get("teams", {})
    lineup_game = modules.get("starting_lineups", {}).get("data", {}).get("teams", {})
    player_rows = player_history if isinstance(player_history, list) else player_history.get("players", []) if isinstance(player_history, dict) else []
    unmatched = evidence.get("unmatched_candidates", [])
    unresolved_out = [claim for claim in unmatched
                      if str(claim.get("status", "")).strip().casefold() in ("out", "inactive", "ruled out", "suspended")]
    if unresolved_out:
        return {"game_id": gid, "home_team": fixture["home_team"], "away_team": fixture["away_team"],
                "base_home_probability": fixture["hybrid_p_home"],
                "base_away_probability": 1.0 - fixture["hybrid_p_home"],
                "status": "blocked", "reason": "unmatched_or_team_conflicting_out_claims",
                "unresolved_out_claims": unresolved_out, "teams": {},
                "margin_sample_games": len(margins), "logistic_margin_scale_points": scale,
                "calibrated": False, "production_approved": False,
                "secondary_consensus_out_count": 0, "official_out_count": 0}
    row = {"game_id": gid, "home_team": fixture["home_team"], "away_team": fixture["away_team"],
           "base_home_probability": fixture["hybrid_p_home"],
           "base_away_probability": 1.0 - fixture["hybrid_p_home"],
           "status": "blocked", "reason": None, "source_rule": "official OUT; otherwise matching CBS Sports + ESPN OUT claims",
           "teams": {}, "margin_sample_games": len(margins), "logistic_margin_scale_points": scale,
           "calibrated": False, "production_approved": False, "base_prediction_changed": False,
           "secondary_consensus_out_count": 0, "official_out_count": 0}
    parsed = {}
    reasons = []
    for team in (fixture["home_team"], fixture["away_team"]):
        impact, reason = _multi_source_team_points(team, availability_game.get(team, {}),
            rotation_game.get(team, {}), lineup_game.get(team, {}), player_rows,
            teams_evidence.get(team, []), emitted.isoformat(), fixture["tipoff_utc"])
        row["teams"][team] = impact or {"status": "unavailable"}
        if reason == "no_secondary_provider_consensus_out":
            # Official-only effects are already computed by the primary model.
            if impact and impact.get("secondary_consensus_out_count", 0) == 0:
                parsed[team] = {"net_points_per_game": 0.0,
                                "official_out_count": impact.get("official_out_count", 0),
                                "secondary_consensus_out_count": 0}
            continue
        if reason:
            reasons.append(team + ":" + reason)
        else:
            parsed[team] = {"net_points_per_game": impact["estimated_net_points_per_game"],
                            "official_out_count": impact["official_out_count"],
                            "secondary_consensus_out_count": impact["secondary_consensus_out_count"],
                            "secondary_provider_out_count": impact.get("secondary_provider_out_count", 0)}
    row["official_out_count"] = sum(value["official_out_count"] for value in parsed.values())
    row["secondary_consensus_out_count"] = sum(value["secondary_consensus_out_count"] for value in parsed.values())
    row["uncertain_status_probability_range"] = _uncertain_probability_range(
        fixture, teams_evidence, availability_game, rotation_game, lineup_game,
        player_rows, emitted, scale, unmatched)
    if reasons:
        row["reason"] = ";".join(reasons)
        return row
    row["secondary_provider_out_count"] = sum(value.get("secondary_provider_out_count", 0) for value in parsed.values())
    if row["secondary_provider_out_count"] < 1:
        row["status"] = "no_secondary_provider_out"
        row["reason"] = "No non-conflicting, roster-matched pre-tip OUT claim from CBS Sports or ESPN was available."
        return row
    if scale is None:
        row["reason"] = "fewer_than_100_pre_emission_historical_margins"
        return row
    points_delta = parsed[fixture["home_team"]]["net_points_per_game"] - parsed[fixture["away_team"]]["net_points_per_game"]
    raw_delta = points_delta / scale
    applied_delta = max(-MAX_ABS_LOG_ODDS_DELTA, min(MAX_ABS_LOG_ODDS_DELTA, raw_delta))
    base = fixture["hybrid_p_home"]
    base_logit = math.log(base / (1.0 - base))
    adjusted = 1.0 / (1.0 + math.exp(-(base_logit + applied_delta)))
    row.update({"status": "research_scenario", "reason": None,
        "estimated_home_points_delta": points_delta, "raw_log_odds_delta": raw_delta,
        "applied_log_odds_delta": applied_delta,
        "log_odds_delta_capped": not math.isclose(raw_delta, applied_delta, rel_tol=0, abs_tol=1e-12),
        "injury_adjusted_home_probability": adjusted,
        "injury_adjusted_away_probability": 1.0 - adjusted,
        "home_probability_delta_pp": (adjusted - base) * 100.0,
        "method": "roster_matched_out_claims_and_historical_minute_redistribution_then_logistic_margin_scale",
        "assumptions": ["Official NBA OUT claims are accepted as official evidence.",
            "Secondary OUT claims require exact roster identity and no matched source conflict; one CBS or ESPN provider is enough for an experimental candidate, with two-source agreement preserved when available.",
            "NBC editorial headlines do not count as independent provider confirmation.",
            "Player scoring rates are linear in historical redistributed minutes.",
            "Questionable, doubtful and unknown statuses are not treated as OUT; single-source questionable/doubtful statuses are evaluated only as unweighted conditional branches.",
            "Logistic margin scale uses up to 1000 completed pre-emission games.",
            "Research scenario only; it is not calibrated or production-approved."]})
    return row


def build(snapshot, module_context, history, player_history=None):
    _verify_seal(snapshot)
    _verify_seal(module_context)
    if module_context.get("snapshot_sha256") != snapshot.get("content_sha256"):
        raise ValueError("Module context does not match the frozen forecast")
    emitted = utc(snapshot["created_at_utc"])
    source_games = module_context.get("games", {})
    if set(source_games) != {str(row["game_id"]) for row in snapshot.get("predictions", [])}:
        raise ValueError("Module context must cover the complete frozen slate")
    margins = _history_margins(history, emitted)
    scale = None
    if len(margins) >= MIN_MARGIN_HISTORY:
        standard_deviation = statistics.pstdev(margins)
        if math.isfinite(standard_deviation) and standard_deviation > 0:
            # A logistic distribution with this scale has the observed margin SD.
            scale = standard_deviation * math.sqrt(3.0) / math.pi
    output = []
    for fixture in snapshot["predictions"]:
        gid = str(fixture["game_id"])
        tipoff = utc(fixture["tipoff_utc"])
        base = fixture.get("hybrid_p_home")
        if not _number(base) or not 0 < base < 1:
            raise ValueError("Invalid statistical baseline probability")
        row = {"game_id": gid, "home_team": fixture["home_team"], "away_team": fixture["away_team"],
               "tipoff_utc": fixture["tipoff_utc"], "status": "blocked",
               "reason": None, "base_home_probability": base, "base_away_probability": 1.0 - base,
               "injury_adjusted_home_probability": None, "injury_adjusted_away_probability": None,
               "home_probability_delta_pp": None, "estimated_home_points_delta": None,
               "teams": {}, "margin_sample_games": len(margins), "logistic_margin_scale_points": scale,
               "calibrated": False, "production_approved": False, "base_prediction_changed": False}
        if emitted >= tipoff:
            row["reason"] = "forecast_not_pregame"
            output.append(row)
            continue
        source_scenario = _multi_source_research_scenario(
            fixture, source_games[gid], history, player_history or [], emitted, margins, scale)
        row["multi_source_scenario"] = source_scenario
        modules = source_games[gid].get("availability_impact", {})
        scenario = modules.get("conditional_production_scenario", {})
        if scenario.get("baseline_snapshot_sha256") != snapshot.get("content_sha256"):
            row["reason"] = "availability_scenario_snapshot_mismatch"
            output.append(row)
            continue
        team_inputs = scenario.get("games", {}).get(gid, {}).get("teams", {})
        parsed = {}
        reasons = []
        for team in (fixture["home_team"], fixture["away_team"]):
            team_data = team_inputs.get(team, {})
            impact, reason = _team_points(team_data)
            row["teams"][team] = {"official_out_count": team_data.get("official_out_count", 0),
                "out_players": impact["out_players"] if impact else [],
                "estimated_points_lost_per_game": impact["points_lost_per_game"] if impact else None,
                "estimated_points_added_by_replacements_per_game": impact["points_added_per_game"] if impact else None,
                "estimated_net_points_per_game": impact["net_points_per_game"] if impact else None,
                "unresolved_status_count": team_data.get("players_without_confirmed_availability"),
                "lineup_role_weights_applied": (team_data.get("minute_redistribution") or {}).get("lineup_role_weights_applied", 0),
                "lineup_role_players": (team_data.get("minute_redistribution") or {}).get("lineup_role_players", []),
                "lineup_evidence_status": (team_data.get("minute_redistribution") or {}).get("lineup_evidence_status")}
            if reason:
                reasons.append(team + ":" + reason)
            else:
                parsed[team] = impact
        if reasons:
            row["reason"] = ";".join(reasons)
            output.append(row)
            continue
        total_out = sum(item["official_out_count"] for item in parsed.values())
        if total_out == 0:
            row["status"] = "no_confirmed_out_claims"
            row["reason"] = "No exact, official OUT claims were matched for either team."
            output.append(row)
            continue
        if scale is None:
            row["reason"] = "fewer_than_100_pre_emission_historical_margins"
            output.append(row)
            continue
        home = fixture["home_team"]
        away = fixture["away_team"]
        points_delta = parsed[home]["net_points_per_game"] - parsed[away]["net_points_per_game"]
        raw_log_odds_delta = points_delta / scale
        applied_log_odds_delta = max(-MAX_ABS_LOG_ODDS_DELTA,
                                     min(MAX_ABS_LOG_ODDS_DELTA, raw_log_odds_delta))
        base_logit = math.log(base / (1.0 - base))
        adjusted = 1.0 / (1.0 + math.exp(-(base_logit + applied_log_odds_delta)))
        row.update({"status": "research_scenario", "reason": None,
            "estimated_home_points_delta": points_delta,
            "raw_log_odds_delta": raw_log_odds_delta,
            "applied_log_odds_delta": applied_log_odds_delta,
            "log_odds_delta_capped": not math.isclose(raw_log_odds_delta, applied_log_odds_delta, rel_tol=0, abs_tol=1e-12),
            "injury_adjusted_home_probability": adjusted,
            "injury_adjusted_away_probability": 1.0 - adjusted,
            "home_probability_delta_pp": (adjusted - base) * 100.0,
            "method": "historical_points_and_minute_redistribution_then_logistic_margin_scale",
            "assumptions": ["Only uniquely matched official NBA OUT claims are applied.",
                "Player scoring rates are linear in the conditional redistributed minutes.",
                "Questionable, doubtful and unknown statuses are not treated as OUT.",
                "Logistic margin scale is estimated from up to 1000 pre-emission completed games.",
                "Research sensitivity only; it is not independently calibrated or production-approved."]})
        output.append(row)
    body = {"schema_version": 1, "model_version": "NBA_MULTI_SOURCE_INJURY_PROBABILITY_RESEARCH_V2",
            "snapshot_sha256": snapshot["content_sha256"], "created_at_utc": snapshot["created_at_utc"],
            "games": output, "calibrated": False, "production_approved": False,
            "changes_statistical_baseline": False, "no_odds_input": True}
    body["content_sha256"] = digest(body)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "module-context", "history", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--player-history")
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    player_history = load(args.player_history) if args.player_history else []
    report = build(load(args.snapshot), load(args.module_context), load(args.history), player_history)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"games": len(report["games"]),
                      "research_scenarios": sum(row["status"] == "research_scenario" for row in report["games"]),
                      "multi_source_scenarios": sum(row.get("multi_source_scenario", {}).get("status") == "research_scenario" for row in report["games"]),
                      "production_approved": False}))


if __name__ == "__main__":
    main()
