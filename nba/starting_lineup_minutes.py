"""Role-conditioned minute weights from a timestamped RotoWire starting five.

Historical starter labels are used only to estimate a player's minutes when
starting. Current lineups must be sourced and observed before tipoff. This
module supplies weights to the injury replacement scenario; it never treats
projected starters as confirmed availability.
"""
from datetime import datetime, timezone
import math
from urllib.parse import urlparse
import unicodedata


def _name_key(value):
    return "".join(char for char in unicodedata.normalize("NFKD", str(value or "").casefold())
                   if char.isalnum())


def resolve_starter_ids(members, names):
    """Match exact names or a unique first-initial/surname pair to roster IDs."""
    resolved = []
    for supplied in names:
        key = _name_key(supplied)
        matches = [row for row in members if _name_key(row.get("player")) == key]
        if not matches:
            tokens = str(supplied or "").strip().split()
            if len(tokens) >= 2 and len(tokens[0].replace(".", "")) == 1:
                initial, surname = tokens[0][0].casefold(), _name_key(tokens[-1])
                matches = []
                for row in members:
                    player_tokens = [_name_key(token) for token in str(row.get("player") or "").split()]
                    if player_tokens and player_tokens[-1] == surname and player_tokens[0][:1] == initial:
                        matches.append(row)
        if len(matches) != 1 or not matches[0].get("player_id"):
            return []
        resolved.append(str(matches[0]["player_id"]))
    return resolved if len(resolved) == 5 and len(set(resolved)) == 5 else []


def utc(value):
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None or moment.utcoffset() != timezone.utc.utcoffset(moment):
        raise ValueError("Explicit UTC timestamp required")
    return moment.astimezone(timezone.utc)


def estimate(team, roster_team, player_history, emitted_at, tipoff):
    lineup_status = roster_team.get("lineup_status")
    source = roster_team.get("lineup_source_url")
    observed = roster_team.get("lineup_observed_at_utc")
    host = (urlparse(str(source)).hostname or "").lower()
    if not (lineup_status in ("projected", "confirmed") and host.endswith("rotowire.com")):
        return {"status": "lineup_source_unavailable", "weights": {}, "players": []}
    try:
        observed_at = utc(observed)
        emitted = utc(emitted_at)
        start = utc(tipoff)
    except (TypeError, ValueError):
        return {"status": "invalid_lineup_timestamp", "weights": {}, "players": []}
    if observed_at > emitted or observed_at >= start:
        return {"status": "lineup_not_observed_before_issue_and_tipoff", "weights": {}, "players": []}
    starters = [p for p in roster_team.get("players", []) if p.get("starter_projected") is True]
    ids = [str(p.get("player_id") or "") for p in starters]
    if len(starters) != 5 or any(not pid for pid in ids) or len(set(ids)) != 5:
        return {"status": "five_unique_roster_matched_starters_required", "weights": {}, "players": []}
    rows = player_history if isinstance(player_history, list) else player_history.get("players", [])
    by_id = {pid: [] for pid in ids}
    for row in rows:
        pid = str(row.get("player_id") or "")
        if pid not in by_id or row.get("team") != team or row.get("starter_reported_postgame") is not True:
            continue
        try:
            if utc(row["tipoff_utc"]) >= start or utc(row["observed_at_utc"]) > emitted:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        minutes = row.get("minutes_played")
        if (row.get("did_not_play") or type(minutes) not in (int, float)
                or not math.isfinite(minutes) or minutes <= 0):
            continue
        by_id[pid].append((utc(row["tipoff_utc"]), float(minutes)))
    details = []
    weights = {}
    for player, pid in zip(starters, ids):
        history = sorted(by_id[pid])[-5:]
        if len(history) < 2:
            return {"status": "insufficient_historical_starter_minutes", "weights": {},
                    "players": [{"player_id": pid, "player": player.get("player"),
                                 "starter_games": len(history)}]}
        weight = sum(minutes for _, minutes in history) / len(history)
        weights[pid] = weight
        details.append({"player_id": pid, "player": player.get("player"),
                        "position": player.get("position_abbreviation"),
                        "starter_games": len(history), "average_minutes_when_starting": round(weight, 2)})
    return {"status": "role_weights_ready", "weights": weights, "players": details,
            "source_url": source, "observed_at_utc": observed,
            "lineup_status": lineup_status,
            "method": "mean_last_five_prior_starts_minimum_two"}


def apply_role_weights(rotation_samples, starter_evidence, history_by_player=None):
    """Replace generic player-minute weights with observed starter-role means."""
    history_by_player = history_by_player or {}
    details = {str(row.get("player_id")): row for row in starter_evidence.get("players", [])}
    applied = []
    for raw_id, weight in starter_evidence.get("weights", {}).items():
        pid = str(raw_id)
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight <= 0:
            continue
        row = rotation_samples.get(pid)
        if row is None:
            historical = history_by_player.get(pid, {})
            row = {"player_id": pid, "player": details.get(pid, {}).get("player"),
                   "sample_games": historical.get("minutes_sample_games", 0)}
            rotation_samples[pid] = row
        row["minutes_projection"] = float(weight)
        row["projection_method"] = "mean_last_five_prior_starts_minimum_two"
        row["lineup_role_weight_applied"] = True
        row["position_abbreviation"] = details.get(pid, {}).get("position")
        applied.append(pid)
    return applied
