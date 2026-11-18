"""Descriptive team-level NHL shot profile from official Gamecenter events.

Postgame features only. It is intentionally not connected to prediction weights;
team attribution, coordinate semantics, temporal coverage, and calibration must
be demonstrated before any expected-goal or probability adjustment is enabled.
"""
import math
from collections import Counter

SHOT_TYPES = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
LOCATION_TYPES = {"shot-on-goal", "missed-shot", "goal"}
# NHL rink coordinates use feet; the two goal lines are approximately +/- 89 ft.
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
    value = _first_value(event, ("eventOwnerTeamId", "teamId", "eventTeamId"))
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


def _empty_counts(team, team_id):
    return {
        "team": team,
        "team_id": team_id,
        "games": 0,
        "attacks": Counter(),
        "distance_bins_ft": Counter(),
        "shot_types": Counter(),
        "located_unblocked_shots": 0,
        "invalid_or_missing_location": 0,
    }


def _finish(counts):
    attacks = dict(sorted(counts["attacks"].items()))
    bins = counts["distance_bins_ft"]
    located = counts["located_unblocked_shots"]
    all_events = attacks.get("shot_events", 0)
    close = bins.get("0-25", 0)
    output = {
        "team": counts["team"],
        "team_id": counts["team_id"],
        "team_games_in_sample": counts["games"],
        "shot_events": all_events,
        "shots_on_goal": attacks.get("shot-on-goal", 0) + attacks.get("goal", 0),
        "missed_shots": attacks.get("missed-shot", 0),
        "blocked_shot_events": attacks.get("blocked-shot", 0),
        "goals": attacks.get("goal", 0),
        "located_unblocked_shots": located,
        "distance_bins_ft": {key: bins.get(key, 0) for key in ("0-25", "25-40", "40+")},
        "within_25ft_share": round(close / located, 5) if located else None,
        "shot_types": dict(sorted(counts["shot_types"].items())),
        "invalid_or_missing_location": counts["invalid_or_missing_location"],
    }
    return output


def game_profile(fixture, plays):
    """Summarize one completed game without assigning unmatched events to teams."""
    team_info = {
        int(fixture["home_team_id"]): (fixture["home"], fixture["away"]),
        int(fixture["away_team_id"]): (fixture["away"], fixture["home"]),
    }
    counts = {team_id: _empty_counts(names[0], team_id) for team_id, names in team_info.items()}
    for row in counts.values():
        row["games"] = 1
    unassigned = Counter()
    location_anomalies = []
    for event in plays:
        if not isinstance(event, dict):
            continue
        kind = _event_type(event)
        if kind not in SHOT_TYPES:
            continue
        owner = _team_id(event)
        if owner not in counts:
            unassigned[kind] += 1
            continue
        row = counts[owner]
        row["attacks"]["shot_events"] += 1
        row["attacks"][kind] += 1
        shot_type = _first_value(event, ("shotType",))
        if shot_type is not None:
            row["shot_types"][str(shot_type)] += 1
        if kind not in LOCATION_TYPES:
            continue
        x = _coordinate(event, ("xCoord", "xCoordOrigin"))
        y = _coordinate(event, ("yCoord", "yCoordOrigin"))
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
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    return {
        "game_id": str(fixture["game_id"]),
        "date": fixture["date"],
        "home": fixture["home"],
        "away": fixture["away"],
        "source_class": "postgame_event_features_for_future_games_only",
        "team_profiles": {
            counts[home_id]["team"]: _finish(counts[home_id]),
            counts[away_id]["team"]: _finish(counts[away_id]),
        },
        "unassigned_shot_events": dict(sorted(unassigned.items())),
        "location_anomalies": location_anomalies,
        "event_schema": {
            "team_owner_id_found": sum(row["attacks"].get("shot_events", 0) for row in counts.values())
                                  + sum(unassigned.values()),
            "coordinate_assumption": "distance to nearer goal line at x=+/-89 ft; profile is descriptive, not official NHL danger classification",
        },
        "applied_to_prediction": False,
        "calibrated": False,
    }


def aggregate_profiles(game_profiles):
    teams = {}
    for game in game_profiles:
        for team, profile in game.get("team_profiles", {}).items():
            target = teams.setdefault(team, _empty_counts(team, profile.get("team_id")))
            target["games"] += 1
            target["located_unblocked_shots"] += profile.get("located_unblocked_shots", 0)
            target["invalid_or_missing_location"] += profile.get("invalid_or_missing_location", 0)
            for key in ("shot-on-goal", "missed-shot", "blocked-shot", "goal", "shot_events"):
                value = profile.get({
                    "shot-on-goal": "shots_on_goal",
                    "missed-shot": "missed_shots",
                    "blocked-shot": "blocked_shot_events",
                    "goal": "goals",
                    "shot_events": "shot_events",
                }[key], 0)
                if key == "shot-on-goal":
                    value = max(0, value - profile.get("goals", 0))
                target["attacks"][key] += value
            for key, value in profile.get("distance_bins_ft", {}).items():
                target["distance_bins_ft"][key] += value
            target["shot_types"].update(profile.get("shot_types", {}))
    return {
        team: {
            **_finish(counts),
            "coverage_status": "descriptive_sample_only",
            "prediction_effect": 0.0,
        }
        for team, counts in sorted(teams.items())
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
