"""Descriptive NBA player prop history; never a betting probability."""
import math
from statistics import fmean

METRICS = (
    ("pra", "PRA", "points_rebounds_assists"),
    ("three_pointers_made", "Triples", "three_points_made"),
    ("rebounds", "Rebotes", "rebounds"),
    ("free_throws_made", "Tiros libres", "free_throws_made"),
)

def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def _metric_value(row, key):
    if key == "points_rebounds_assists":
        values = (row.get("points"), row.get("rebounds"), row.get("assists"))
        return sum(values) if all(_number(value) for value in values) else None
    value = row.get(key)
    return value if _number(value) else None

def _summary(rows, average):
    home = [row for row in rows if row.get("is_home") is True]
    away = [row for row in rows if row.get("is_home") is False]
    def split(items):
        values = [row["value"] for row in items]
        return {
            "games": len(values),
            "average": round(fmean(values), 2) if values else None,
            "at_or_above_season_average": sum(value >= average for value in values) if values else 0,
        }
    return {
        "games": len(rows),
        "season_average": round(average, 2) if rows else None,
        "at_or_above_season_average": sum(row["value"] >= average for row in rows),
        "home": split(home),
        "away": split(away),
    }

def build_player_stats_props(history_rows, *, season_end_year, opponent_team):
    """Summarize only captured games in the current NBA season.

    Hit counts compare each game with that player's own captured-season mean.
    They describe past results and are not prop-line probabilities.
    """
    season_rows = [
        row for row in history_rows
        if row.get("season_end_year") == season_end_year
        and not row.get("did_not_play")
        and type(row.get("minutes_played")) in (int, float)
        and math.isfinite(row["minutes_played"])
        and row["minutes_played"] > 0
    ]
    season_rows.sort(key=lambda row: (str(row.get("tipoff_utc") or ""), str(row.get("game_id") or "")))
    opponent = str(opponent_team or "").upper()
    result = {
        "season_end_year": season_end_year,
        "opponent_team": opponent or None,
        "history_games": len(season_rows),
        "history_from_utc": season_rows[0].get("tipoff_utc") if season_rows else None,
        "history_through_utc": season_rows[-1].get("tipoff_utc") if season_rows else None,
        "comparison_basis": "captured_current_season_mean",
        "metrics": {},
        "note": "Historical results compared with the player's mean in the captured current-season sample; not a betting line or probability.",
    }
    for key, label, source_key in METRICS:
        games = []
        for row in season_rows:
            value = _metric_value(row, source_key)
            if value is None:
                continue
            is_home = row.get("is_home")
            if type(is_home) is not bool:
                continue
            game = {
                "game_id": str(row.get("game_id") or ""),
                "tipoff_utc": row.get("tipoff_utc"),
                "opponent_team": row.get("opponent_team"),
                "is_home": is_home,
                "value": value,
            }
            attempted_key = {"three_pointers_made": "three_points_attempted",
                             "free_throws_made": "free_throws_attempted"}.get(key)
            if attempted_key:
                attempted = row.get(attempted_key)
                game["attempted"] = attempted if _number(attempted) else None
            games.append(game)
        average = fmean(row["value"] for row in games) if games else None
        for game in games:
            game["at_or_above_season_average"] = (
                game["value"] >= average if average is not None else None
            )
        matchup = [game for game in games
                   if opponent and str(game.get("opponent_team") or "").upper() == opponent]
        matchup_summary = _summary(matchup, average) if average is not None else None
        result["metrics"][key] = {
            "label": label,
            "summary": _summary(games, average) if average is not None else {
                "games": 0, "season_average": None, "at_or_above_season_average": 0,
                "home": {"games": 0, "average": None, "at_or_above_season_average": 0},
                "away": {"games": 0, "average": None, "at_or_above_season_average": 0},
            },
            "matchup": matchup_summary,
            "games": games,
        }
    return result
