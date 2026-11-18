"""Experimental, point-in-time division/rivalry adjustment for NHL goal rates.

Uses only official completed-game regulation goals from dates strictly before
the target slate. It is a shrunk historical feature, not a calibrated effect.
"""
from datetime import date, timedelta
import csv
import hashlib
from pathlib import Path

from nhl.module_audit import DIVISIONS, RIVALRIES

TEAM_DIVISION = {team: index for index, division in enumerate(DIVISIONS) for team in division}
MIN_DIVISION_GAMES = 12
MIN_OTHER_GAMES = 12
MIN_RIVALRY_GAMES = 4
WINDOW_DAYS = 730
SHRINKAGE_GAMES = 20
MAX_DIFFERENTIAL_DELTA = 0.35


def load_history(path):
    """Read official postgame labels and return their immutable provenance."""
    source = Path(path)
    raw = source.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows:
        raise ValueError("Division/rivalry history is empty")
    label_dates = sorted(
        str(row.get("date")) for row in rows
        if row.get("date") and len(str(row.get("date"))) == 10
    )
    metadata = {
        "path": source.relative_to(Path.cwd()).as_posix() if source.is_relative_to(Path.cwd()) else source.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows),
        "first_label_date": label_dates[0] if label_dates else None,
        "latest_label_date": label_dates[-1] if label_dates else None,
        "source": "NHL official Gamecenter labels, regulation scores",
    }
    return rows, metadata


def _valid_rows(labels, cutoff):
    cutoff_day = date.fromisoformat(cutoff)
    earliest = cutoff_day - timedelta(days=WINDOW_DAYS)
    valid = []
    for row in labels or []:
        try:
            game_day = date.fromisoformat(str(row["date"]))
            home, away = str(row["home"]), str(row["away"])
            if game_day >= cutoff_day or game_day < earliest:
                continue
            if home not in TEAM_DIVISION or away not in TEAM_DIVISION or home == away:
                continue
            if row.get("data_class") != "POSTGAME_LABELS_NOT_PREGAME_FEATURES":
                continue
            home_goals = int(row["rt_home_goals"])
            away_goals = int(row["rt_away_goals"])
            if home_goals < 0 or away_goals < 0:
                continue
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        valid.append({
            "date": game_day,
            "home": home,
            "away": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "divisional": TEAM_DIVISION[home] == TEAM_DIVISION[away],
        })
    return valid


def _team_split(games, team):
    divisional, other = [], []
    for game in games:
        if game["home"] == team:
            opponent = game["away"]
            differential = game["home_goals"] - game["away_goals"]
        elif game["away"] == team:
            opponent = game["home"]
            differential = game["away_goals"] - game["home_goals"]
        else:
            continue
        (divisional if TEAM_DIVISION[team] == TEAM_DIVISION[opponent] else other).append(differential)
    return divisional, other


def _mean(values):
    return sum(values) / len(values) if values else None


def estimate(home, away, cutoff, labels, source=None):
    """Estimate a bounded differential shift from strictly prior two-year history."""
    if home not in TEAM_DIVISION or away not in TEAM_DIVISION or home == away:
        raise ValueError("Unknown or duplicate NHL team for division/rivalry")
    date.fromisoformat(cutoff)
    games = _valid_rows(labels, cutoff)
    divisional = TEAM_DIVISION[home] == TEAM_DIVISION[away]
    tier = RIVALRIES.get(frozenset((home, away)))
    result = {
        "status": "context_only",
        "divisional": divisional,
        "rivalry": tier is not None,
        "rivalry_tier": tier,
        "history_window_days": WINDOW_DAYS,
        "cutoff_exclusive": cutoff,
        "historical_games_eligible": len(games),
        "expected_goal_differential_delta": 0.0,
        "home_expected_goals_delta": 0.0,
        "away_expected_goals_delta": 0.0,
        "applied_to_percentages": False,
        "calibrated": False,
        "source": source,
        "evidence": {},
    }
    if not divisional:
        result["reason"] = "teams_are_not_in_the_same_division"
        return result

    home_div, home_other = _team_split(games, home)
    away_div, away_other = _team_split(games, away)
    result["evidence"] = {
        home: {"division_games": len(home_div), "other_games": len(home_other),
               "division_goal_diff_per_game": _mean(home_div),
               "other_goal_diff_per_game": _mean(home_other)},
        away: {"division_games": len(away_div), "other_games": len(away_other),
               "division_goal_diff_per_game": _mean(away_div),
               "other_goal_diff_per_game": _mean(away_other)},
    }
    if (min(len(home_div), len(away_div)) < MIN_DIVISION_GAMES
            or min(len(home_other), len(away_other)) < MIN_OTHER_GAMES):
        result["status"] = "insufficient_history"
        result["reason"] = "minimum_division_and_other_opponent_samples_not_met"
        return result

    def shrunk_split(div_values, other_values):
        reliability = min(
            len(div_values) / (len(div_values) + SHRINKAGE_GAMES),
            len(other_values) / (len(other_values) + SHRINKAGE_GAMES),
        )
        return (_mean(div_values) - _mean(other_values)) * reliability

    delta = 0.5 * (shrunk_split(home_div, home_other) - shrunk_split(away_div, away_other))
    result["division_adjustment_goal_differential"] = delta

    rivalry_games = [
        game for game in games
        if {game["home"], game["away"]} == {home, away}
    ]
    result["evidence"]["head_to_head_games"] = len(rivalry_games)
    if tier and len(rivalry_games) >= MIN_RIVALRY_GAMES:
        home_h2h = [
            g["home_goals"] - g["away_goals"] if g["home"] == home
            else g["away_goals"] - g["home_goals"]
            for g in rivalry_games
        ]
        home_other_div, away_other_div = [], []
        for game in games:
            for team, excluded_opponent, destination in (
                (home, away, home_other_div),
                (away, home, away_other_div),
            ):
                if team not in (game["home"], game["away"]):
                    continue
                opponent = game["away"] if game["home"] == team else game["home"]
                if opponent == excluded_opponent or TEAM_DIVISION[team] != TEAM_DIVISION[opponent]:
                    continue
                differential = (game["home_goals"] - game["away_goals"]
                                if game["home"] == team
                                else game["away_goals"] - game["home_goals"])
                destination.append(differential)
        if len(home_other_div) >= MIN_OTHER_GAMES and len(away_other_div) >= MIN_OTHER_GAMES:
            h2h_mean = _mean(home_h2h)
            peer_baseline = 0.5 * (_mean(home_other_div) - _mean(away_other_div))
            h2h_reliability = len(rivalry_games) / (len(rivalry_games) + SHRINKAGE_GAMES)
            peer_reliability = min(
                len(home_other_div) / (len(home_other_div) + SHRINKAGE_GAMES),
                len(away_other_div) / (len(away_other_div) + SHRINKAGE_GAMES),
            )
            rivalry_delta = (h2h_mean - peer_baseline) * h2h_reliability * peer_reliability
            result["rivalry_adjustment_goal_differential"] = rivalry_delta
            delta += rivalry_delta
        else:
            result["rivalry_adjustment_goal_differential"] = 0.0
    else:
        result["rivalry_adjustment_goal_differential"] = 0.0

    delta = max(-MAX_DIFFERENTIAL_DELTA, min(MAX_DIFFERENTIAL_DELTA, delta))
    result.update({
        "status": "applied" if abs(delta) > 1e-9 else "eligible_no_directional_signal",
        "reason": "historical_goal_differential_split_shrunk_to_zero",
        "expected_goal_differential_delta": delta,
        "home_expected_goals_delta": delta / 2,
        "away_expected_goals_delta": -delta / 2,
        "applied_to_percentages": abs(delta) > 1e-9,
    })
    return result
