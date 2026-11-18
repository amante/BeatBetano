"""Descriptive NHL team attack/defense shot profile from official Gamecenter events.

Postgame features only. It is intentionally not connected to prediction weights;
team attribution, coordinate semantics, temporal coverage, and calibration must
be demonstrated before any expected-goal or probability adjustment is enabled.
"""
import math
from collections import Counter

SHOT_TYPES = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
LOCATION_TYPES = {"shot-on-goal", "missed-shot", "goal"}
GOAL_X = (-89.0, 89.0)
MAX_ABS_X = 100.0
MAX_ABS_Y = 50.0


def _flatten_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _flatten_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_dicts(child)


def _first_value(event, aliases):
    for row in _flatten_dicts(event):
        for alias in aliases:
            if alias in row and row[alias] is not None:
                return row[alias]
    return None


def _event_type(event):
    value = _first_value(event, ("typeDescKey", "typeCode", "eventType"))
    return str(value or "unknown").strip().lower().replace("_", "-")


def _team_id(event):
    value = _first_value(event, ("eventOwnerTeamId",))
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _coordinate(event, aliases):
    value = _first_value(event, aliases)
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)


def _distance_to_nearest_goal(x, y):
    return min(math.hypot(x - goal_x, y) for goal_x in GOAL_X)


def _empty_counts():
    return {
        "shot_events": 0,
        "shots_on_goal": 0,
        "missed_shots": 0,
        "blocked_shot_events": 0,
        "goals": 0,
        "located_unblocked_shots": 0,
        "invalid_or_missing_location": 0,
        "distance_bins_ft": Counter(),
        "shot_types": Counter(),
    }


def _finish(counts):
    located = counts["located_unblocked_shots"]
    return {
        "shot_events": counts["shot_events"],
        "shots_on_goal": counts["shots_on_goal"],
        "missed_shots": counts["missed_shots"],
        "blocked_shot_events": counts["blocked_shot_events"],
        "goals": counts["goals"],
        "located_unblocked_shots": located,
        "distance_bins_ft": {key: counts["distance_bins_ft"].get(key, 0)
                             for key in ("0-25", "25-40", "40+")},
        "within_25ft_share": round(counts["distance_bins_ft"].get("0-25", 0) / located, 5)
                             if located else None,
        "shot_types": dict(sorted(counts["shot_types"].items())),
        "invalid_or_missing_location": counts["invalid_or_missing_location"],
    }


def _summarize_events(plays, team_info):
    counts = {team_id: _empty_counts() for team_id in team_info}
    unassigned = Counter()
    all_x, all_y = [], []
    location_anomalies = []
    for event in plays:
        if not isinstance(event, dict):
            continue
        kind = _event_type(event)
        if kind not in SHOT_TYPES:
            continue
        x = _coordinate(event, ("xCoord", "xCoordOrigin"))
        y = _coordinate(event, ("yCoord", "yCoordOrigin"))
        if x is not None:
            all_x.append(x)
        if y is not None:
            all_y.append(y)
        owner = _team_id(event)
        if owner not in counts:
            unassigned[kind] += 1
            continue
        row = counts[owner]
        row["shot_events"] += 1
        if kind in ("shot-on-goal", "goal"):
            row["shots_on_goal"] += 1
        if kind == "missed-shot":
            row["missed_shots"] += 1
        if kind == "blocked-shot":
            row["blocked_shot_events"] += 1
        if kind == "goal":
            row["goals"] += 1
        shot_type = _first_value(event, ("shotType",))
        if shot_type is not None:
            row["shot_types"][str(shot_type)] += 1
        # Blocked-shot coordinates can mark the block, not the shot origin.
        if kind not in LOCATION_TYPES:
            continue
        if x is None or y is None or abs(x) > MAX_ABS_X or abs(y) > MAX_ABS_Y:
            row["invalid_or_missing_location"] += 1
            if len(location_anomalies) < 5:
                location_anomalies.append({"event_id": _first_value(event, ("eventId", "id")),
                                           "x": x, "y": y, "reason": "missing_or_out_of_rink_bounds"})
            continue
        distance = _distance_to_nearest_goal(x, y)
        row["located_unblocked_shots"] += 1
        if distance <= 25:
            row["distance_bins_ft"]["0-25"] += 1
        elif distance <= 40:
            row["distance_bins_ft"]["25-40"] += 1
        else:
            row["distance_bins_ft"]["40+"] += 1
    coordinates = {
        "shot_events_with_x": len(all_x), "shot_events_with_y": len(all_y),
        "x_min": min(all_x) if all_x else None, "x_max": max(all_x) if all_x else None,
        "y_min": min(all_y) if all_y else None, "y_max": max(all_y) if all_y else None,
        "units_verified": False,
    }
    return counts, dict(sorted(unassigned.items())), location_anomalies, coordinates


def game_profile(fixture, plays):
    """Summarize one completed game; never assign an unowned event by inference."""
    team_info = {
        int(fixture["home_team_id"]): fixture["home"],
        int(fixture["away_team_id"]): fixture["away"],
    }
    counts, unassigned, anomalies, coordinate_diagnostics = _summarize_events(plays, team_info)
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    teams = {}
    for team_id, opponent_id in ((home_id, away_id), (away_id, home_id)):
        teams[team_info[team_id]] = {
            "team_id": team_id,
            "team_games_in_sample": 1,
            "attack": _finish(counts[team_id]),
            "defense_allowed": _finish(counts[opponent_id]),
        }
    return {
        "game_id": str(fixture["game_id"]),
        "date": fixture["date"],
        "home": fixture["home"],
        "away": fixture["away"],
        "source_class": "postgame_event_features_for_future_games_only",
        "team_profiles": teams,
        "unassigned_shot_events": unassigned,
        "location_anomalies": anomalies,
        "coordinate_diagnostics": coordinate_diagnostics,
        "coordinate_assumption": "distance to nearer goal line at x=+/-89 ft; descriptive geometry, not official NHL danger classification",
        "applied_to_prediction": False,
        "calibrated": False,
    }


def _aggregate_component(rows):
    totals = _empty_counts()
    games = 0
    for row in rows:
        games += 1
        for key in ("shot_events", "shots_on_goal", "missed_shots", "blocked_shot_events",
                    "goals", "located_unblocked_shots", "invalid_or_missing_location"):
            totals[key] += int(row.get(key, 0) or 0)
        totals["distance_bins_ft"].update(row.get("distance_bins_ft", {}))
        totals["shot_types"].update(row.get("shot_types", {}))
    return {"games": games, **_finish(totals)}


def aggregate_profiles(game_profiles):
    teams = {}
    for game in game_profiles:
        for team, profile in game.get("team_profiles", {}).items():
            teams.setdefault(team, {"team_id": profile.get("team_id"), "attack": [], "defense": []})
            teams[team]["attack"].append(profile.get("attack", {}))
            teams[team]["defense"].append(profile.get("defense_allowed", {}))
    return {
        team: {
            "team_id": data["team_id"],
            "attack": _aggregate_component(data["attack"]),
            "defense_allowed": _aggregate_component(data["defense"]),
            "coverage_status": "descriptive_sample_only",
            "prediction_effect": 0.0,
        }
        for team, data in sorted(teams.items())
    }


def build_report(game_profiles):
    return {
        "kind": "nhl_opponent_style_team_profile_v1",
        "games": game_profiles,
        "teams": aggregate_profiles(game_profiles),
        "applied_to_prediction": False,
        "calibrated": False,
        "limitations": [
            "Profiles summarize a bounded postgame sample and are not pregame features for those same games.",
            "Shot-event team attribution requires an explicit event owner team ID; unmatched events remain unassigned.",
            "Distance bands use nearest-goal geometry and are not NHL EDGE danger labels or a fitted expected-goals model.",
            "Blocked-shot events are counted but excluded from shot-origin distance because their coordinates may describe the block location.",
            "No on-ice matchup, line chemistry, score-state, or manpower adjustment is inferred.",
            "No probabilities are changed by this descriptive profile.",
        ],
    }
