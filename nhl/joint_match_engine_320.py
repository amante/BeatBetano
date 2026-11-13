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


VERSION = "nhl-joint-match-320-v1"


def _num(value, label, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing or invalid " + label)
    if value < 0 or (positive and value <= 0):
        raise ValueError("Out-of-range " + label)
    return float(value)


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
        group_audit[group] = {"target_minutes": target,
                              "full_target_minutes": full_target,
                              "unresolved_reserved_minutes": full_target-target,
                              "modeled_player_count": len(members),
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
                   "historical_reference_minutes": historical_reference,
                   "reference_minutes": baseline_budget,
                   "full_reference_minutes": full_reference_budget,
                   "unresolved_reserved_minutes": full_reference_budget-baseline_budget,
                   "partial_projection": partial,
                   "allocated_minutes": sum(x["total"] for x in result.values()),
                   "incoming_player_ids": sorted(incoming_ids), "by_group": group_audit}


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
    active_ids = {p["player_id"] for p in skaters}
    change_data = team.get("lineup_changes", {})
    incoming = list(change_data.get("new_in_projection", []))
    incoming_ids = {p.get("player_id") for p in incoming}
    outgoing = list(change_data.get("out_of_projection", []))
    outgoing_by_id = {p.get("player_id"): p for p in outgoing if p.get("player_id") is not None}
    for player in team.get("unavailable_players", []):
        pid = player.get("player_id")
        if pid is not None and pid not in active_ids and pid not in outgoing_by_id and player.get("production"):
            outgoing.append(player)
            outgoing_by_id[pid] = player

    if partial_lineup:
        team_games = _num(summary.get("gamesPlayed"), "team games", positive=True)
        aggregate, residual = partial_ledger["base"], partial_ledger["residual"]
        baseline_totals = {"minutes":300.0, "goals":aggregate["goals"],
                           "assists":aggregate["assists"], "shots":aggregate["shots"],
                           "pim":aggregate["penaltyMinutes"]}
        known_projected = {key:sum(item["projected"][key] for item in player_contributions)
                           for key in ("minutes","goals","assists","shots","pim")}
        projected_totals = {
            "minutes":300.0,
            "goals":residual["goals"]+known_projected["goals"],
            "assists":residual["assists"]+known_projected["assists"],
            "shots":residual["shots"]+known_projected["shots"],
            "pim":residual["penaltyMinutes"]+known_projected["pim"],
        }
    else:
        prior_ids = {p["player_id"] for p in skaters if p["player_id"] not in incoming_ids}
        baseline_totals = {key: 0.0 for key in ("minutes", "goals", "assists", "shots", "pim")}
        baseline_group_totals = {group: {key: 0.0 for key in baseline_totals}
                                 for group in ("forwards", "defense")}
        for player in outgoing:
            contribution = _historical_contribution(player)
            group = "defense" if player.get("position") == "D" else "forwards"
            for key in baseline_totals:
                baseline_totals[key] += contribution[key]
                baseline_group_totals[group][key] += contribution[key]
        for player in skaters:
            if player["player_id"] in prior_ids:
                item = next(item for item in player_contributions if item["player_id"] == player["player_id"])
                contribution = item["baseline"]
                group = item["unit"]
                for key in baseline_totals:
                    baseline_totals[key] += contribution[key]
                    baseline_group_totals[group][key] += contribution[key]
        for group, target in (("forwards", 180.0), ("defense", 120.0)):
            reference = baseline_group_totals[group]["minutes"]
            scale = target / reference if reference > 0 else 0.0
            for key in ("goals", "assists", "shots", "pim"):
                baseline_group_totals[group][key] *= scale
            baseline_group_totals[group]["minutes"] = target
        for key in baseline_totals:
            baseline_totals[key] = sum(baseline_group_totals[group][key] for group in baseline_group_totals)
        projected_totals = {key: sum(item["projected"][key] for item in player_contributions)
                            for key in baseline_totals}

    outgoing_totals = {key: 0.0 for key in ("minutes", "goals", "assists", "shots", "pim")}
    for player in outgoing:
        if player.get("production") and player.get("games_played"):
            values = _historical_contribution(player)
            for key in outgoing_totals:
                outgoing_totals[key] += values[key]
    incoming_totals = {key: 0.0 for key in ("minutes", "goals", "assists", "shots", "pim")}
    for item in player_contributions:
        if item["player_id"] in incoming_ids:
            for key in incoming_totals:
                incoming_totals[key] += item["projected"][key]
    lineup_impact = {
        "out_of_projection": [
            {"player_id": p.get("player_id"), "name": p.get("name"),
             "contribution_per_game": _historical_contribution(p)}
            for p in outgoing if p.get("production") and p.get("games_played")
        ],
        "out_of_projection_total_per_game": outgoing_totals,
        "incoming_total_after_reallocation_per_game": incoming_totals,
        "incoming_to_projected_lineup": [
            {"player_id": item["player_id"], "name": item["name"],
             "projected_contribution_per_game": item["projected"],
             "minute_and_production_delta_vs_historical_usage": item["delta"]}
            for item in player_contributions if item["player_id"] in incoming_ids
        ],
        "team_net_change_vs_previous_roster_per_game": {
            key: projected_totals[key] - baseline_totals[key] for key in baseline_totals
        },
        "projected_lineup_totals_per_game": projected_totals,
        "reference_lineup_totals_per_game": baseline_totals,
        "partial_projection": partial_lineup,
        "identity_coverage": coverage if partial_lineup else None,
        "unresolved_roster_residual_per_game": residual if partial_lineup else None,
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
        "rates": rates,
        "credit_ratios": credit_ratios,
        "goal_event_rates_from_player_points": event_rates,
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
    non_pp_rate = attacking["goal_event_rates_from_player_points"]["EV"] * shot_factor

    # Estimate penalty opportunities from both clubs' dated special-team
    # counts. Active opponent PIM exposure adjusts opportunities empirically.
    own_pp = attacking["special"]["pp_per_game"]
    opp_pk_opps = defending["special"]["pk_opportunities_per_game"]
    expected_pp_opps = (own_pp + opp_pk_opps) / 2 * defending["penalty_rate_ratio"]
    own_pp_rate = attacking["special"]["pp_goal_rate"]
    opp_pk_leak = defending["special"]["pk_goals_allowed_rate"]
    if own_pp_rate is None or opp_pk_leak is None or league_pk_rate <= 0:
        raise ValueError("Incomplete PP/PK rates")
    pp_lineup_goals = attacking["goal_event_rates_from_player_points"]["PP"] * expected_pp_opps / max(1e-9, own_pp)
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
    rate = (non_pp_rate + pp_rate + short_handed_rate) * goalie_factor
    if not math.isfinite(rate) or rate <= 0 or rate >= 10:
        raise ValueError("Unsupported expected goal rate")
    return {
        "expected_goals": rate,
        "components": {
            "projected_ev_goals_per_game": ar["ev_goals"],
            "projected_ev_scoring_events_from_assisted_points": attacking["goal_event_rates_from_player_points"]["EV"],
            "ev_points_per_goal_credit_ratio": attacking["credit_ratios"]["EV"],
            "projected_ev_shots_per_game": ar["ev_shots"],
            "opponent_ev_shots_allowed_proxy": ev_shots_against,
            "expected_ev_shots": expected_ev_shots,
            "ev_shot_matchup_factor": shot_factor,
            "projected_pp_goals_per_game": ar["pp_goals"],
            "projected_pp_scoring_events_from_assisted_points": attacking["goal_event_rates_from_player_points"]["PP"],
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
    home = team_profile(inputs["teams"][home_code], home_code)
    away = team_profile(inputs["teams"][away_code], away_code)
    league_pk_rate = _num(inputs["league_context"].get("powerplay_goals_allowed_per_opportunity"),
                          "league PK rate", positive=True)
    unknowns = list(inputs.get("unknowns", []))
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
            h = _scoring_rate(home, away, ag, league_pk_rate)
            a = _scoring_rate(away, home, hg, league_pk_rate)
            markets = calculate(h["expected_goals"], a["expected_goals"])
            weight=(hg["starter_probability"]*ag["starter_probability"]
                    if hg["starter_probability"] is not None and ag["starter_probability"] is not None else None)
            scenarios.append({"home_goalie": hg, "away_goalie": ag, "scenario_weight": weight,
                              "expected_goals": {"home": h["expected_goals"], "away": a["expected_goals"]},
                              "home_components": h["components"], "away_components": a["components"],
                              "markets": markets})
    weighted_summary=None
    if scenarios and all(s["scenario_weight"] is not None for s in scenarios):
        weight_total=sum(s["scenario_weight"] for s in scenarios)
        if math.isclose(weight_total,1.0,abs_tol=1e-8):
            market_keys=("regulation","illustrative_ml","three_goal_lead","first_to_three_goal_lead")
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
                                  "away":sum(s["scenario_weight"]*s["expected_goals"]["away"] for s in scenarios)},
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
        "source_cutoff_exclusive": cutoff,
        "captured_at_utc": inputs["captured_at_utc"],
        "status": "historical_reconstruction_only" if reconstruction else "conditional_unvalidated_scenarios",
        "publishable": False,
        "scenario_count": len(scenarios),
        "goalie_start_distribution": {home_code: inputs["teams"][home_code].get("goalie_start_distribution"),
                                      away_code: inputs["teams"][away_code].get("goalie_start_distribution")},
        "scenario_weighted_summary": weighted_summary,
        "scenarios": scenarios,
        "minute_distribution": {home_code: home["minute_distribution"],
                                away_code: away["minute_distribution"]},
        "lineup_impact": {home_code: home["lineup_impact"], away_code: away["lineup_impact"]},
        "player_contributions": {home_code: home["player_contributions"],
                                 away_code: away["player_contributions"]},
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
            "Assists describe lineup contribution but are not added as independent goals.",
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
