"""Reconcile multi-source NBA injury claims to fixture-roster player IDs.

This output is a point-in-time evidence ledger only. It records source matches,
source disagreements and unresolved claims without changing the forecast.
"""
import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from team_identity import same_team

ET = ZoneInfo("America/New_York")


def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", str(value or "").casefold())
                         if not unicodedata.combining(c)).split())


def parse_utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


def normalize_status(value):
    key = norm(value).replace("_", " ")
    if key in {"out", "inactive", "suspended", "ruled out", "injured reserve"}:
        return "out"
    if key in {"questionable", "day to day", "day-to-day", "game time decision"}:
        return "questionable"
    if key == "doubtful":
        return "doubtful"
    if key == "probable":
        return "probable"
    if key in {"available", "active", "will play", "available to play"}:
        return "available"
    return None


def _match_name(candidate, roster_players, editorial=False):
    candidate = norm(candidate)
    if not candidate:
        return []
    exact = [p for p in roster_players if norm(p.get("player")) == candidate]
    if exact:
        return exact
    if editorial:
        # Only match full roster names as a complete phrase in a headline.
        # Initials, partial surnames and fuzzy matches remain unresolved.
        return [p for p in roster_players if norm(p.get("player")) and
                re.search(r"(?<![a-z0-9])" + re.escape(norm(p.get("player"))) + r"(?![a-z0-9])", candidate)]
    return []


def _candidate_rows(complement, gid):
    for source in complement.get("sources", []):
        source_name = source.get("source")
        source_type = source.get("source_type")
        for row in source.get("candidates", []):
            if row.get("game_id") and str(row.get("game_id")) != gid:
                continue
            yield source_name, source_type, source, row


def reconcile(snapshot, roster, complement, official=None):
    if roster.get("snapshot_sha256") != snapshot.get("content_sha256"):
        raise ValueError("Current roster snapshot does not match the fixture cohort")
    official = official or {}
    output = {}
    unmatched = []
    invalid_time = []
    conflicts = []
    matched_claims = 0
    all_claims = 0
    for game in snapshot.get("predictions", []):
        gid = str(game["game_id"])
        tip = parse_utc(game.get("tipoff_utc"))
        fixture_teams = (game.get("home_team"), game.get("away_team"))
        fixture_roster = roster.get("games", {}).get(gid, {}).get("teams", {})
        claims_by_player = {}
        game_unmatched = []

        def record_claim(team, player, status, source, source_url, observed, reported,
                         identity_method, editorial=False, source_type=None):
            nonlocal matched_claims, all_claims
            all_claims += 1
            observed_dt = parse_utc(observed)
            reported_dt = parse_utc(reported) if reported else observed_dt
            if not tip or not observed_dt or observed_dt >= tip or not reported_dt or reported_dt > observed_dt:
                invalid_time.append({"game_id": gid, "player": player, "source": source,
                                     "observed_at_utc": observed, "reported_at_utc": reported,
                                     "reason": "not_verified_before_tipoff"})
                return
            state = normalize_status(status)
            if state is None:
                return
            if team not in fixture_teams:
                game_unmatched.append({"source": source, "player": player, "team": team,
                                       "status": state, "reason": "team_not_in_fixture"})
                return
            matched_claims += 1
            claim = {"game_id": gid, "team": team,
                     "player_id": str(player["player_id"]), "player": player["player"],
                     "status": state, "source": source, "source_type": source_type,
                     "source_url": source_url, "observed_at_utc": observed_dt.isoformat(),
                     "reported_at_utc": reported_dt.isoformat() if reported else None,
                     "identity_match": identity_method,
                     "editorial_claim": editorial, "officially_verified": source == "NBA official PDF"}
            claims_by_player.setdefault((team, str(player["player_id"])), []).append(claim)

        for source_name, source_type, source, row in _candidate_rows(complement, gid):
            observed = row.get("observed_at_utc") or source.get("observed_at_utc")
            reported = row.get("reported_at_utc") or row.get("published_at_utc")
            state = row.get("status_candidate") or row.get("status")
            name = row.get("player_candidate") or row.get("player")
            editorial = source_type == "editorial_player_news" or bool(row.get("editorial_claim"))
            headline = row.get("headline")
            matched_players = []
            if name:
                if row.get("player_id"):
                    pid = str(row["player_id"])
                    matched_players = [p for t in fixture_teams
                                       for p in fixture_roster.get(t, {}).get("players", [])
                                       if str(p.get("player_id")) == pid]
                else:
                    matched_players = [p for t in fixture_teams
                                       for p in _match_name(name, fixture_roster.get(t, {}).get("players", []))]
            elif headline and editorial:
                matched_players = [p for t in fixture_teams
                                   for p in _match_name(headline, fixture_roster.get(t, {}).get("players", []), editorial=True)]
            # Deduplicate a player that was included through multiple team loops.
            unique = {(str(p.get("player_id")), p.get("player")): p for p in matched_players}
            matched_players = list(unique.values())
            if len(matched_players) != 1:
                game_unmatched.append({"source": source_name, "candidate": name or headline,
                    "status": state, "reason": "no_unique_exact_roster_match" if not matched_players else "ambiguous_roster_match",
                    "source_url": row.get("source_url") or source.get("url")})
                continue
            player = matched_players[0]
            player_team = next((t for t in fixture_teams if any(
                str(p.get("player_id")) == str(player.get("player_id"))
                for p in fixture_roster.get(t, {}).get("players", []))), None)
            reported_team = row.get("team_candidate") or row.get("team") or row.get("source_team")
            if reported_team and not same_team(reported_team, player_team):
                game_unmatched.append({"source": source_name, "candidate": name or headline,
                    "status": state, "reason": "source_team_conflicts_with_roster_team",
                    "source_team": reported_team, "roster_team": player_team})
                continue
            record_claim(player_team, player, state, source_name or "Unknown source",
                         row.get("source_url") or source.get("url"), observed, reported,
                         "provider_player_id" if row.get("player_id") else "unique_exact_roster_name",
                         editorial=editorial, source_type=source_type)

        # Include only explicitly structured official rows with a pre-tip report
        # timestamp, so conflicts can be shown beside secondary claims.
        report_time = parse_utc(official.get("source_report_as_of_utc"))
        downloaded = parse_utc(official.get("downloaded_at_utc"))
        official_eligible = bool(official.get("official_document_retrieved") is True and tip and
                                 report_time and downloaded and report_time <= downloaded < tip)
        if official_eligible:
            expected_day = tip.astimezone(ET).date()
            for row in official.get("structured_player_rows", []):
                try:
                    row_day = datetime.strptime(str(row.get("game_date")), "%m/%d/%Y").date()
                except ValueError:
                    continue
                if row_day != expected_day:
                    continue
                team = next((t for t in fixture_teams if same_team(row.get("team"), t)), None)
                if not team:
                    continue
                roster_players = fixture_roster.get(team, {}).get("players", [])
                matches = _match_name(row.get("player"), roster_players)
                if len(matches) != 1:
                    game_unmatched.append({"source": "NBA official PDF", "candidate": row.get("player"),
                        "status": row.get("status"), "reason": "no_unique_exact_roster_match"})
                    continue
                record_claim(team, matches[0], row.get("status"), "NBA official PDF",
                             official.get("report_url"), downloaded.isoformat(), report_time.isoformat(),
                             "unique_exact_roster_name", source_type="official_league_report")

        teams = {}
        for (team, pid), claims in sorted(claims_by_player.items()):
            observed_states = sorted({c["status"] for c in claims})
            is_conflict = len(observed_states) > 1
            if is_conflict:
                conflicts.append({"game_id": gid, "team": team, "player_id": pid,
                                  "player": claims[0]["player"], "statuses": observed_states,
                                  "sources": sorted({c["source"] for c in claims})})
            teams.setdefault(team, []).append({"player_id": pid, "player": claims[0]["player"],
                "claims": claims, "status_agreement": observed_states[0] if len(observed_states) == 1 else None,
                "conflict": is_conflict, "model_use": "not_connected_pending_review"})
        output[gid] = {"teams": teams, "unmatched_candidates": game_unmatched,
                       "official_report_used_for_comparison": official_eligible}
        unmatched.extend({"game_id": gid, **row} for row in game_unmatched)
    return {"schema_version": 1, "snapshot_sha256": snapshot.get("content_sha256"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "games": output,
        "matched_claim_count": matched_claims, "claim_candidate_count": all_claims,
        "unmatched_candidate_count": len(unmatched), "unmatched_candidates": unmatched,
        "invalid_or_post_tip_claims": invalid_time, "source_conflicts": conflicts,
        "conflict_count": len(conflicts), "probabilities_changed": False,
        "official_source_available": official.get("official_document_retrieved") is True,
        "note": "Each claim is matched to a unique current-roster player ID and fixture team. Conflicts and editorial observations remain visible and are not model inputs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "roster", "complement", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--official")
    parser.add_argument("--summary")
    args = parser.parse_args()
    read = lambda p: json.loads(Path(p).read_text()) if p and Path(p).is_file() else {}
    result = reconcile(read(args.snapshot), read(args.roster), read(args.complement), read(args.official))
    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False))
    summary = {"games": len(result["games"]), "matched_claims": result["matched_claim_count"],
        "unmatched_candidates": result["unmatched_candidate_count"], "source_conflicts": result["conflict_count"],
        "probabilities_changed": False}
    if args.summary:
        p = Path(args.summary); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# NBA injury source reconciliation\n\n" +
                     "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in summary.items()) +
                     "\n\nOnly unique exact roster matches are joined; unmatched names, team conflicts and source disagreements remain explicit. This evidence is not connected to probabilities in this step.\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
