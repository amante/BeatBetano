"""NBA city-to-city travel and venue-time-zone context; descriptive only.

Distances use representative arena/city coordinates and a great-circle arc,
not actual flight paths. They are context inputs, never probability weights.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from team_identity import canonical

# Team arena coordinates and IANA zones are maintained as a small, auditable
# season-level lookup. Distances should be read as approximate travel distance.
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

def build(snapshot, history):
    freeze = utc(snapshot["created_at_utc"])
    games = sorted((g for g in history if int(g.get("season", 0)) == max(int(x.get("season", 0)) for x in history)
                    and utc(g["tipoff_utc"]) < freeze and g.get("home_points") is not None
                    and g.get("away_points") is not None), key=lambda g: (utc(g["tipoff_utc"]), str(g["game_id"])))
    output = {}
    for fixture in snapshot["predictions"]:
        tip = utc(fixture["tipoff_utc"])
        destination_team = canonical(fixture["home_team"])
        destination = VENUES.get(destination_team)
        teams = {}
        for team_code in (fixture["home_team"], fixture["away_team"]):
            team = canonical(team_code)
            prior = [g for g in games if team in (canonical(g["home_team"]), canonical(g["away_team"]))
                     and utc(g["tipoff_utc"]) < tip]
            last = prior[-1] if prior else None
            if not destination:
                teams[team_code] = {"status": "destination_venue_unknown", "travel_distance_km": None}
                continue
            if not last:
                teams[team_code] = {"status": "no_prior_game_in_current_season", "travel_distance_km": None,
                                    "destination": fixture["home_team"], "destination_time_zone": destination[2]}
                continue
            last_tip = utc(last["tipoff_utc"])
            last_home, last_away = canonical(last["home_team"]), canonical(last["away_team"])
            origin_team = team if last_home == team else last_home
            origin = VENUES.get(origin_team)
            if not origin:
                teams[team_code] = {"status": "origin_venue_unknown", "last_game_id": str(last["game_id"]),
                                    "travel_distance_km": None}
                continue
            origin_local = last_tip.astimezone(ZoneInfo(origin[2]))
            destination_local = tip.astimezone(ZoneInfo(destination[2]))
            gap_hours = (tip - last_tip).total_seconds() / 3600
            teams[team_code] = {
                "status": "estimated_city_to_city_context",
                "last_game_id": str(last["game_id"]), "last_game_tipoff_utc": last_tip.isoformat(),
                "origin_team_home_city": origin_team, "origin_time_zone": origin[2],
                "destination_home_team": fixture["home_team"], "destination_time_zone": destination[2],
                "travel_distance_km": round(distance_km(origin, destination), 1),
                "timezone_shift_hours": round((destination_local.utcoffset() - origin_local.utcoffset()).total_seconds() / 3600, 1),
                "timezone_zone_changed": origin[2] != destination[2],
                "utc_offset_changed": origin_local.utcoffset() != destination_local.utcoffset(),
                "tipoff_gap_hours": round(gap_hours, 1),
                "tipoff_gap_within_24h": gap_hours <= 24,
                "tipoff_gap_within_36h": gap_hours <= 36,
                "distance_method": "great_circle_between_representative_arena_coordinates",
                "flight_path_distance": False,
            }
        output[str(fixture["game_id"])] = {"home_team": fixture["home_team"], "away_team": fixture["away_team"],
            "tipoff_utc": fixture["tipoff_utc"], "teams": teams,
            "probabilities_adjusted": False}
    return {"schema_version": 1, "snapshot_sha256": snapshot["content_sha256"],
            "created_at_utc": snapshot["created_at_utc"], "games": output,
            "no_odds_input": True, "probabilities_adjusted": False,
            "limitations": ["Travel distance is approximate city/arena-to-city/arena great-circle distance, not actual flight route.",
                            "Tipoff gap is not exact rest time because game end time is not modeled.",
                            "These observations have no fitted probability effect."]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True); parser.add_argument("--history", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text()); history = json.loads(Path(args.history).read_text())
    result = build(snapshot, history)
    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as out: json.dump(result, out, indent=2)
    print(json.dumps({"games": len(result["games"]), "teams": sum(len(g["teams"]) for g in result["games"].values()),
                      "distance_estimates": sum(t.get("travel_distance_km") is not None for g in result["games"].values() for t in g["teams"].values()),
                      "probabilities_adjusted": False}, indent=2))

if __name__ == "__main__": main()
