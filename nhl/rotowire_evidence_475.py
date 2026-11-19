"""Reconcile RotoWire NHL pregame observations with official fixture rosters.

RotoWire remains an editorial provider. This module only resolves names against
the captured NHL roster and carries evidence to PULSO; it does not confirm
availability or change model probabilities.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from nhl.nhlcom_lineup_identity import normalized


KIND = "nhl_rotowire_reconciled_pregame_v475"
CAPTURE_KIND = "nhl_rotowire_pregame_capture_454"
STATUS_MAP = {"CONFIRMED", "LIKELY", "EXPECTED", "DTD", "OUT", "IR", "IR-LT", "IR-NR"}


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed


def _resolve(name, roster, role=None):
    if not isinstance(name, str) or not name.strip():
        return {"name": name, "player_id": None, "identity_status": "missing_name"}
    wanted = normalized(name)
    players = roster.get("players", [])
    eligible = [p for p in players if role is None or p.get("position_group") == role]
    exact = [p for p in eligible if normalized(p.get("full_name", "")) == wanted]
    if len(exact) == 1:
        return {"name": name, "player_id": exact[0]["player_id"], "resolved_name": exact[0]["full_name"],
                "identity_status": "exact", "position_group": exact[0].get("position_group")}
    parts = wanted.split()
    initial_matches = []
    if len(parts) >= 2 and len(parts[0]) == 1:
        for player in eligible:
            tokens = normalized(player.get("full_name", "")).split()
            if len(tokens) >= 2 and tokens[0].startswith(parts[0]) and tokens[-1] == parts[-1]:
                if len(parts) == 2 or tokens[1:-1] == parts[1:-1]:
                    initial_matches.append(player)
    if len(initial_matches) == 1:
        player = initial_matches[0]
        return {"name": name, "player_id": player["player_id"], "resolved_name": player["full_name"],
                "identity_status": "unique_initial_and_surname", "position_group": player.get("position_group")}
    return {"name": name, "player_id": None,
            "identity_status": "ambiguous" if exact or initial_matches else "unresolved"}


def _players(section, roster):
    if not isinstance(section, dict):
        return {"status": "not_identified", "players": [], "text": None}
    observed = section.get("players")
    if not isinstance(observed, list):
        observed = []
    result = []
    for item in observed:
        if not isinstance(item, dict):
            continue
        status = item.get("status_observation")
        status = status.upper() if isinstance(status, str) and status.upper() in STATUS_MAP else None
        result.append({
            **_resolve(item.get("name"), roster),
            "position_observation": item.get("position_observation"),
            "reported_status": status,
            "row_text": item.get("row_text"),
            "source_href": item.get("href"),
        })
    return {"status": section.get("status", "not_identified"),
            "players": result, "text": section.get("text")}


def _side(raw_side, roster):
    if not isinstance(raw_side, dict):
        raw_side = {}
    goalie_raw = raw_side.get("goalie")
    goalie = None
    if isinstance(goalie_raw, dict):
        candidate = goalie_raw.get("player")
        if isinstance(candidate, dict):
            goalie = {
                **_resolve(candidate.get("name"), roster, role="goalie"),
                "reported_status": goalie_raw.get("certainty") or candidate.get("status_observation"),
                "source_text": goalie_raw.get("text"),
                "officially_confirmed": False,
            }
    return {
        "capture_status": raw_side.get("status", "not_identified"),
        "players": _players({"players": raw_side.get("players", [])}, roster)["players"],
        "goalie": goalie,
        "power_play_1": _players(raw_side.get("power_play_1"), roster),
        "power_play_2": _players(raw_side.get("power_play_2"), roster),
        "injuries": _players(raw_side.get("injuries"), roster),
    }


def reconcile(report, capture, roster_data, reconciled_at=None):
    if report.get("data_kind") != "source_readiness_only" or report.get("official_predictions") != 0:
        raise ValueError("Expected non-predictive NHL source report")
    if capture.get("kind") != CAPTURE_KIND or capture.get("official") is not False or capture.get("probabilities_modified") is not False:
        raise ValueError("Unexpected RotoWire capture contract")
    captured_at = capture.get("captured_at_utc")
    if not captured_at:
        raise ValueError("RotoWire capture timestamp missing")
    _utc(captured_at)
    source = capture.get("source", {})
    source_hash = source.get("sha256")
    if source_hash is not None and not re.fullmatch(r"[a-f0-9]{64}", source_hash):
        raise ValueError("Invalid RotoWire page hash")
    rosters = roster_data.get("rosters")
    if not isinstance(rosters, list):
        raise ValueError("Official roster list missing")
    roster_by_team = {}
    for row in rosters:
        team = row.get("team")
        if not isinstance(team, str) or team in roster_by_team:
            raise ValueError("Invalid or duplicate official team roster")
        _utc(row.get("as_of"))
        if row.get("as_of") and _utc(row["as_of"]) > _utc(reconciled_at or datetime.now(timezone.utc).isoformat()):
            raise ValueError("Future NHL roster capture")
        roster_by_team[team] = row
    cards = {}
    for card in capture.get("games", []):
        gid = str(card.get("game_id", ""))
        if not gid or gid in cards:
            raise ValueError("Invalid or duplicate RotoWire fixture")
        cards[gid] = card
    now = reconciled_at or datetime.now(timezone.utc).isoformat()
    output = []
    for fixture in report.get("games", []):
        gid = str(fixture.get("game_id", ""))
        card = cards.get(gid)
        start = _utc(fixture["start_utc"])
        available = bool(card and not capture.get("source_error"))
        if card and (card.get("home"), card.get("away")) != (fixture.get("home"), fixture.get("away")):
            raise ValueError("RotoWire fixture identity mismatch")
        if available and (_utc(captured_at) >= start or _utc(now) >= start):
            available = False
        teams = {}
        for side, code in (("home", fixture["home"]), ("away", fixture["away"])):
            roster = roster_by_team.get(code)
            if available and roster:
                observation = _side(card.get(side + "_observation"), roster)
                observation["status"] = "observed"
                observation["identity_coverage"] = {
                    "players": sum(p.get("player_id") is not None for p in observation["players"]),
                    "player_observations": len(observation["players"]),
                }
            else:
                observation = {
                    "status": "unavailable",
                    "reason": "source_capture_missing" if not card or capture.get("source_error") else
                              "roster_identity_unavailable" if not roster else "capture_not_pregame",
                    "players": [], "goalie": None,
                    "power_play_1": {"status": "not_identified", "players": [], "text": None},
                    "power_play_2": {"status": "not_identified", "players": [], "text": None},
                    "injuries": {"status": "not_identified", "players": [], "text": None},
                }
            teams[code] = observation
        output.append({
            "game_id": gid, "home": fixture["home"], "away": fixture["away"],
            "start_utc": fixture["start_utc"],
            "status": "observed" if available else "unavailable",
            "teams": teams,
            "market_observation": card.get("market_observation") if available else None,
            "source": {"provider": "RotoWire", "url": source.get("source_url"),
                       "captured_at_utc": captured_at, "page_sha256": source_hash,
                       "card_sha256": card.get("source_card_sha256") if card else None,
                       "official": False},
            "probabilities_modified": False,
        })
    return {
        "kind": KIND, "captured_at_utc": captured_at, "reconciled_at_utc": now,
        "source_error": capture.get("source_error"),
        "games": output, "probabilities_modified": False, "official": False,
        "note": "RotoWire evidence is attached to fixture identities; projected goalie, PP and injury statuses remain provider observations.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--rosters", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--public-out")
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    try:
        result = reconcile(read(args.report), read(args.capture), read(args.rosters))
    except Exception as error:
        report = read(args.report)
        result = {
            "kind": KIND, "captured_at_utc": None,
            "games": [{"game_id": str(game["game_id"]), "home": game["home"], "away": game["away"],
                       "start_utc": game["start_utc"], "status": "unavailable",
                       "teams": {}, "market_observation": None,
                       "probabilities_modified": False,
                       "reason": type(error).__name__ + ": " + str(error)[:200]}
                      for game in report.get("games", [])],
            "source_error": type(error).__name__ + ": " + str(error)[:200],
            "probabilities_modified": False, "official": False,
        }
    for path in (args.out, args.public_out):
        if path:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"games": len(result["games"]),
                      "observed": sum(game["status"] == "observed" for game in result["games"]),
                      "probabilities_modified": False}))


if __name__ == "__main__":
    main()
