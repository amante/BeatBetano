"""Archive NBA +20 first-passage and maximum-lead observations after settlement.

One postgame fetch per settled game. Missing or malformed play-by-play is recorded
as unavailable; no forecast probability or coefficient is changed.
"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


PBP_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"


def number_score(value):
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _lead_side(margin):
    return 1 if margin > 0 else -1 if margin < 0 else 0


def _period_clock(play):
    period = play.get("period")
    if isinstance(period, dict):
        period = period.get("number")
    try:
        period = int(period)
    except (TypeError, ValueError):
        period = None
    clock = play.get("clock")
    if isinstance(clock, dict):
        clock = clock.get("displayValue")
    if not isinstance(clock, str):
        clock = None
    return period, clock


def _clock_seconds(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\\s*(\\d{1,2}):(\\d{2})\\s*", value)
    if match:
        minutes, seconds = int(match.group(1)), int(match.group(2))
        if seconds < 60:
            return minutes * 60 + seconds
    match = re.fullmatch(r"PT(?:(\\d+)M)?(?:(\\d+(?:\\.\\d+)?)S)?", value)
    if match:
        return float(match.group(1) or 0) * 60 + float(match.group(2) or 0)
    return None


def parse_game(payload, fixture, outcome_home, content_sha256, fetched_at_utc):
    header = payload.get("header", {}) if isinstance(payload, dict) else {}
    competitions = header.get("competitions", []) if isinstance(header, dict) else []
    if not competitions or str(competitions[0].get("id")) != str(fixture["game_id"]):
        raise ValueError("play_by_play_game_id_mismatch")
    competitors = competitions[0].get("competitors", [])
    final_scores = {}
    for competitor in competitors:
        side = competitor.get("homeAway")
        score = number_score(competitor.get("score"))
        if side in ("home", "away") and score is not None:
            final_scores[side] = score
    if set(final_scores) != {"home", "away"}:
        raise ValueError("official_final_scores_missing")

    plays = payload.get("plays")
    if not isinstance(plays, list):
        nested = payload.get("playByPlay") or {}
        plays = nested.get("plays") if isinstance(nested, dict) else None
    if not isinstance(plays, list) or len(plays) < 2:
        raise ValueError("play_by_play_plays_missing")

    indexed = list(enumerate(plays))
    parsed_clocks = [_period_clock(play) for play in plays if isinstance(play, dict)]
    if len(parsed_clocks) == len(plays) and all(period is not None and _clock_seconds(clock) is not None for period, clock in parsed_clocks):
        indexed.sort(key=lambda pair: (
            _period_clock(pair[1])[0],
            -_clock_seconds(_period_clock(pair[1])[1]),
            pair[0],
        ))

    home_score = away_score = 0
    max_home = {"points": 0, "period": None, "clock": None, "play_id": None}
    max_away = {"points": 0, "period": None, "clock": None, "play_id": None}
    first_home_20 = None
    first_away_20 = None
    previous_nonzero_sign = 0
    lead_changes = 0
    score_observations = 0

    for index, action in indexed:
        if not isinstance(action, dict):
            continue
        next_home = number_score(action.get("homeScore", action.get("scoreHome")))
        next_away = number_score(action.get("awayScore", action.get("scoreAway")))
        if next_home is not None:
            home_score = next_home
        if next_away is not None:
            away_score = next_away
        if next_home is None and next_away is None:
            continue
        score_observations += 1
        margin = home_score - away_score
        sign = _lead_side(margin)
        period, clock = _period_clock(action)
        point = {"period": period, "clock": clock,
                 "play_id": str(action.get("id", action.get("sequenceNumber", index)))}
        if margin > max_home["points"]:
            max_home = {"points": margin, **point}
        if -margin > max_away["points"]:
            max_away = {"points": -margin, **point}
        if margin >= 20 and first_home_20 is None:
            first_home_20 = {"lead_points": margin, **point}
        if margin <= -20 and first_away_20 is None:
            first_away_20 = {"lead_points": -margin, **point}
        if sign and previous_nonzero_sign and sign != previous_nonzero_sign:
            lead_changes += 1
        if sign:
            previous_nonzero_sign = sign

    if score_observations < 2:
        raise ValueError("play_by_play_score_path_incomplete")
    if (home_score, away_score) != (final_scores["home"], final_scores["away"]):
        raise ValueError("play_by_play_score_path_does_not_match_final_box")
    if home_score == away_score:
        raise ValueError("play_by_play_final_tie_unresolved")
    actual_home = int(home_score > away_score)
    if type(outcome_home) is not int or outcome_home not in (0, 1) or actual_home != outcome_home:
        raise ValueError("play_by_play_final_outcome_mismatch")
    return {
        "game_id": str(fixture["game_id"]),
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "tipoff_utc": fixture["tipoff_utc"],
        "play_by_play_status": "verified_against_settled_score",
        "final_score": {"home": home_score, "away": away_score},
        "max_home_lead": max_home,
        "max_away_lead": max_away,
        "either_team_reached_plus20": first_home_20 is not None or first_away_20 is not None,
        "first_home_plus20": first_home_20,
        "first_away_plus20": first_away_20,
        "lead_changes": lead_changes,
        "score_observations": score_observations,
        "play_events": len(plays),
        "source_url": PBP_URL.format(game_id=fixture["game_id"]),
        "source_sha256": content_sha256,
        "fetched_at_utc": fetched_at_utc,
    }

def collect(snapshot, settled, session=None):
    fixtures = {str(row["game_id"]): row for row in snapshot.get("predictions", [])}
    outcome_rows = {str(row.get("game_id")): row for row in settled.get("games", [])}
    client = session or requests.Session()
    completed = []
    unavailable = []
    for game_id, result in sorted(outcome_rows.items()):
        fixture = fixtures.get(game_id)
        if fixture is None:
            unavailable.append({"game_id": game_id, "status": "not_in_frozen_snapshot"})
            continue
        url = PBP_URL.format(game_id=game_id)
        try:
            response = client.get(url, timeout=(5, 20), headers={"User-Agent": "BeatBetano postgame validation"})
            response.raise_for_status()
            raw = response.content
            payload = response.json()
            report = parse_game(payload, fixture, result.get("outcome_home"),
                                hashlib.sha256(raw).hexdigest(),
                                datetime.now(timezone.utc).isoformat())
            completed.append(report)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            unavailable.append({"game_id": game_id, "status": "unavailable_or_invalid",
                                "error_type": type(exc).__name__,
                                "reason": str(exc)[:160]})
    ranked = []
    for row in completed:
        for side, team, lead in (
            ("home", row["home_team"], row["max_home_lead"]),
            ("away", row["away_team"], row["max_away_lead"]),
        ):
            ranked.append({"game_id": row["game_id"], "team": team, "opponent": row["away_team"] if side == "home" else row["home_team"],
                           "side": side, "maximum_lead_points": lead["points"],
                           "period": lead["period"], "clock": lead["clock"],
                           "tipoff_utc": row["tipoff_utc"]})
    ranked.sort(key=lambda item: (-item["maximum_lead_points"], item["tipoff_utc"], item["game_id"], item["side"]))
    return {
        "schema_version": 1,
        "kind": "nba_plus20_trajectory_validation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot_sha256": snapshot.get("content_sha256"),
        "settled_games_requested": len(outcome_rows),
        "games_with_verified_score_path": len(completed),
        "games_unavailable": len(unavailable),
        "plus20_games": sum(row["either_team_reached_plus20"] for row in completed),
        "five_largest_observed_advantages": ranked[:5],
        "games": completed,
        "unavailable_games": unavailable,
        "model_probabilities_modified": False,
        "calibrated": False,
        "production_approved": False,
        "limitations": [
            "The report records observed scoring paths; it does not estimate the probability of a future +20 lead.",
            "Only play-by-play records whose final winner agrees with the settled result are retained as verified.",
            "A largest lead is descriptive and does not measure its cause or validate a forecast.",
            "Unavailable source data is listed per game and does not block the base postmortem.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--settled", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text())
    settled = json.loads(Path(args.settled).read_text())
    report = collect(snapshot, settled)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(json.dumps({
        "settled_games_requested": report["settled_games_requested"],
        "verified_score_paths": report["games_with_verified_score_path"],
        "five_largest_advantages": report["five_largest_observed_advantages"],
        "probabilities_modified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
