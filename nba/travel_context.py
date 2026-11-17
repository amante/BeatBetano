"""NBA rest, back-to-back, workload, travel and time-zone context.

All distances are approximate great-circle arena distances. Rest is measured
tipoff-to-tipoff; game duration and actual flight itineraries are unavailable.
This module captures pregame evidence only and never changes probabilities.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from team_identity import canonical

VENUES = {
    "ATL": (33.7573, -84.3963, "America/New_York"),
    "BOS": (42.3662, -71.0621, "America/New_York"),
    "BKN": (40.6826, -73.9754, "America/New_York"),
    "CHA": (35.2251, -80.8392, "America/New_York"),
    "CHI": (41.8807, -87.6742, "America/Chicago"),
    "CLE": (41.4965, -81.6882, "America/New_York"),
    "DAL": (32.7905, -96.8103, "America/Chicago"),
    "DEN": (39.7487, -105.0077, "America/Denver"),
    "DET": (42.3410, -83.0550, "America/Detroit"),
    "GS": (37.7680, -122.3877, "America/Los_Angeles"),
    "HOU": (29.7508, -95.3621, "America/Chicago"),
    "IND": (39.7640, -86.1555, "America/Indiana/Indianapolis"),
    "LAC": (33.9535, -118.3392, "America/Los_Angeles"),
    "LAL": (34.0430, -118.2673, "America/Los_Angeles"),
    "MEM": (35.1382, -90.0506, "America/Chicago"),
    "MIA": (25.7814, -80.1870, "America/New_York"),
    "MIL": (43.0451, -87.9172, "America/Chicago"),
    "MIN": (44.9795, -93.2760, "America/Chicago"),
    "NO": (29.9490, -90.0821, "America/Chicago"),
    "NY": (40.7505, -73.9934, "America/New_York"),
    "OKC": (35.4634, -97.5151, "America/Chicago"),
    "ORL": (28.5392, -81.3839, "America/New_York"),
    "PHI": (39.9012, -75.1720, "America/New_York"),
    "PHX": (33.4457, -112.0712, "America/Phoenix"),
    "POR": (45.5316, -122.6668, "America/Los_Angeles"),
    "SAC": (38.5802, -121.4997, "America/Los_Angeles"),
    "SA": (29.4270, -98.4375, "America/Chicago"),
    "TOR": (43.6435, -79.3791, "America/Toronto"),
    "UTAH": (40.7683, -111.9011, "America/Denver"),
    "WSH": (38.8981, -77.0209, "America/New_York"),
}
EARTH_KM = 6371.0088


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("UTC timestamp required")
    return parsed.astimezone(timezone.utc)


def distance_km(a, b):
    lat1, lon1 = map(math.radians, a[:2])
    lat2, lon2 = map(math.radians, b[:2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_KM * 2 * math.asin(min(1.0, math.sqrt(h)))


def _game_venue(team, game):
    """Arena where team played in game; returns NBA venue code or None."""
    home = canonical(game.get("home_team"))
    away = canonical(game.get("away_team"))
    if team == home:
        return home, True
    if team == away:
        return home, False
    return None, None


def _team_context(team, is_home, tip, history, destination_code, destination):
    prior = []
    for game in history:
        try:
            if utc(game["tipoff_utc"]) >= tip:
                continue
            venue, team_was_home = _game_venue(team, game)
            if venue:
                prior.append((utc(game["tipoff_utc"]), game, venue, team_was_home))
        except (KeyError, TypeError, ValueError):
            continue
    prior.sort(key=lambda item: (item[0], str(item[1].get("game_id", ""))))
    last = prior[-1] if prior else None
    base = {"status": "no_prior_game_in_current_season" if not last else "estimated_city_to_city_context",
            "is_home": bool(is_home), "destination_home_team": destination_code,
            "destination_time_zone": destination[2] if destination else None}
    if not last:
        home_venue = VENUES.get(team)
        local_tip = tip.astimezone(ZoneInfo(destination[2])) if destination else None
        body_clock = tip.astimezone(ZoneInfo(home_venue[2])) if home_venue else local_tip
        base.update({"rest_days": None, "tipoff_gap_hours": None, "is_back_to_back": False,
                     "back_to_back_path": None, "games_last_4_days": 0, "games_last_7_days": 0,
                     "travel_distance_km": None, "timezone_shift_hours": None,
                     "body_clock_tipoff_hour": round(body_clock.hour + body_clock.minute / 60, 1) if body_clock else None,
                     "body_clock_reference": "home_timezone_fallback_no_prior_game"})
        return base
    last_tip, last_game, origin_code, previous_home = last
    origin = VENUES.get(origin_code)
    gap_hours = max(0.0, (tip - last_tip).total_seconds() / 3600)
    # NBA schedule back-to-back is approximated using local arena dates and
    # tipoff gap; actual game-end/rest hours are not present in the feed.
    b2b = False
    local_day_gap = None
    timezone_shift = None
    body_clock_hour = None
    if origin and destination:
        origin_local = last_tip.astimezone(ZoneInfo(origin[2]))
        destination_local = tip.astimezone(ZoneInfo(destination[2]))
        local_day_gap = (destination_local.date() - origin_local.date()).days
        b2b = gap_hours <= 36 and 0 <= local_day_gap <= 1
        timezone_shift = round((destination_local.utcoffset() - origin_local.utcoffset()).total_seconds() / 3600, 1)
        body_clock_hour = round(tip.astimezone(ZoneInfo(origin[2])).hour
                                + tip.astimezone(ZoneInfo(origin[2])).minute / 60, 1)
    else:
        b2b = gap_hours <= 36
    current_venue = destination_code
    current_home = bool(is_home)
    path = None
    if b2b:
        path = ("home" if previous_home else "road") + "_to_" + ("home" if current_home else "road")
    games_4d = sum(1 for when, _, _, _ in prior if 0 < (tip - when).total_seconds() <= 4 * 86400)
    games_7d = sum(1 for when, _, _, _ in prior if 0 < (tip - when).total_seconds() <= 7 * 86400)
    recent = [item for item in prior if 0 < (tip - item[0]).total_seconds() <= 7 * 86400]
    route = [(item[0], item[2]) for item in recent]
    route.append((tip, current_venue))
    cumulative_distance = 0.0
    cumulative_signed_shift = 0.0
    cumulative_absolute_shift = 0.0
    for (left_tip, left_venue), (right_tip, right_venue) in zip(route, route[1:]):
        left_info, right_info = VENUES.get(left_venue), VENUES.get(right_venue)
        if not left_info or not right_info:
            continue
        cumulative_distance += distance_km(left_info, right_info)
        left_offset = left_tip.astimezone(ZoneInfo(left_info[2])).utcoffset()
        right_offset = right_tip.astimezone(ZoneInfo(right_info[2])).utcoffset()
        shift = (right_offset - left_offset).total_seconds() / 3600
        cumulative_signed_shift += shift
        cumulative_absolute_shift += abs(shift)
    base.update({
        "last_game_id": str(last_game.get("game_id", "")),
        "last_game_tipoff_utc": last_tip.isoformat(),
        "last_game_was_home": bool(previous_home),
        "last_game_venue": origin_code,
        "tipoff_gap_hours": round(gap_hours, 1),
        "rest_days": max(0, min(7, int(gap_hours // 24) - 1)),
        "local_calendar_days_since_last_game": local_day_gap,
        "is_back_to_back": b2b,
        "back_to_back_path": path,
        "games_last_4_days": games_4d,
        "games_last_7_days": games_7d,
        "travel_distance_km": round(distance_km(origin, destination), 1) if origin and destination else None,
        "cumulative_travel_km_last_7_days": round(cumulative_distance, 1),
        "cumulative_timezone_shift_hours_last_7_days": round(cumulative_signed_shift, 1),
        "cumulative_absolute_timezone_shift_hours_last_7_days": round(cumulative_absolute_shift, 1),
        "origin_time_zone": origin[2] if origin else None,
        "body_clock_reference": "previous_game_local_timezone",
        "timezone_shift_hours": timezone_shift,
        "timezone_zone_changed": bool(origin and destination and origin[2] != destination[2]),
        "body_clock_tipoff_hour": body_clock_hour,
        "distance_method": "great_circle_between_representative_arena_coordinates",
        "flight_path_distance": False,
    })
    return base


def game_context(home_team, away_team, tipoff_utc, history):
    home = canonical(home_team)
    away = canonical(away_team)
    destination = VENUES.get(home)
    tip = utc(tipoff_utc)
    teams = {}
    for code, is_home in ((home_team, True), (away_team, False)):
        team = canonical(code)
        teams[code] = _team_context(team, is_home, tip, history, home, destination)
    return teams


def build(snapshot, history):
    freeze = utc(snapshot["created_at_utc"])
    rows = history if isinstance(history, list) else history.get("games", [])
    seasons = [int(g.get("season", 0)) for g in rows if str(g.get("season", "")).isdigit()]
    current_season = max(seasons) if seasons else None
    completed = []
    for game in rows:
        try:
            if current_season is not None and int(game.get("season", 0)) != current_season:
                continue
            if utc(game["tipoff_utc"]) < freeze and game.get("home_points") is not None and game.get("away_points") is not None:
                completed.append(game)
        except (KeyError, TypeError, ValueError):
            continue
    output = {}
    for fixture in snapshot["predictions"]:
        teams = game_context(fixture["home_team"], fixture["away_team"], fixture["tipoff_utc"], completed)
        output[str(fixture["game_id"])] = {
            "home_team": fixture["home_team"], "away_team": fixture["away_team"],
            "tipoff_utc": fixture["tipoff_utc"], "teams": teams,
            "probabilities_adjusted": False,
        }
    return {"schema_version": 2, "snapshot_sha256": snapshot["content_sha256"],
            "created_at_utc": snapshot["created_at_utc"], "games": output,
            "no_odds_input": True, "probabilities_adjusted": False,
            "research_basis": [
                {"title": "Impacts of travel distance and travel direction on back-to-back games in the NBA",
                 "url": "https://pubmed.ncbi.nlm.nih.gov/34170248/"},
                {"title": "Associations of circadian change, travel distance, and their interaction with NBA performance",
                 "url": "https://pubmed.ncbi.nlm.nih.gov/35980109/"},
                {"title": "Eastward Jet Lag is Associated with Impaired Performance and Game Outcome in the NBA",
                 "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9245584/"},
            ],
            "limitations": [
                "Rest is tipoff-to-tipoff; game end time and actual travel itinerary are unavailable.",
                "B2B is estimated from local arena dates and a maximum 36-hour gap.",
                "Travel distance is approximate arena-to-arena great-circle distance, not flight distance.",
                "Rest, B2B, schedule load and travel evidence do not change probabilities in this context file.",
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text())
    history = json.loads(Path(args.history).read_text())
    result = build(snapshot, history)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as out:
        json.dump(result, out, indent=2)
    teams = [team for game in result["games"].values() for team in game["teams"].values()]
    print(json.dumps({"games": len(result["games"]), "teams": len(teams),
                      "travel_estimates": sum(t.get("travel_distance_km") is not None for t in teams),
                      "b2b_teams": sum(t.get("is_back_to_back") is True for t in teams),
                      "probabilities_adjusted": False}, indent=2))


if __name__ == "__main__":
    main()
