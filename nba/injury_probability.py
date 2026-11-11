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


def build(snapshot, module_context, history):
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
    body = {"schema_version": 1, "model_version": "NBA_CONFIRMED_INJURY_PROBABILITY_RESEARCH_V1",
            "snapshot_sha256": snapshot["content_sha256"], "created_at_utc": snapshot["created_at_utc"],
            "games": output, "calibrated": False, "production_approved": False,
            "changes_statistical_baseline": False, "no_odds_input": True}
    body["content_sha256"] = digest(body)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "module-context", "history", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    report = build(load(args.snapshot), load(args.module_context), load(args.history))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"games": len(report["games"]),
                      "research_scenarios": sum(row["status"] == "research_scenario" for row in report["games"]),
                      "production_approved": False}))


if __name__ == "__main__":
    main()
