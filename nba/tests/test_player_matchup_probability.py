import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from player_matchup_probability import (
    _result_rows, assign_by_position, build, digest
)


class PlayerMatchupProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.issued = "2026-11-10T19:00:00Z"
        self.home = [{"player_id": f"h{i}", "player": f"Home {i}", "position": pos}
                     for i, pos in enumerate(("PG", "SG", "SF", "PF", "C"))]
        self.away = [{"player_id": f"a{i}", "player": f"Away {i}", "position": pos}
                     for i, pos in enumerate(("PG", "SG", "SF", "PF", "C"))]
        body = {"created_at_utc": self.issued, "predictions": [
            {"game_id": "g1", "home_team": "BOS", "away_team": "NYK",
             "tipoff_utc": "2026-11-10T23:00:00Z", "hybrid_p_home": 0.5}]}
        self.snapshot = dict(body, content_sha256=digest(body))
        context_body = {"snapshot_sha256": self.snapshot["content_sha256"], "games": {
            "g1": {"player_matchups": {"data": {"teams": {
                "BOS": {"lineup_status": "projected",
                        "lineup_source": "https://www.rotowire.com/basketball/nba-lineups.php",
                        "reported_starters": self.home},
                "NYK": {"lineup_status": "projected",
                        "lineup_source": "https://www.rotowire.com/basketball/nba-lineups.php",
                        "reported_starters": self.away}}}}}}}
        self.context = dict(context_body, content_sha256=digest(context_body))
        history = []
        for i in range(120):
            day = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            history.append({"tipoff_utc": day.isoformat().replace("+00:00", "Z"),
                "observed_at_utc": day.isoformat().replace("+00:00", "Z"),
                "home_points": 110 + i % 2 * 10, "away_points": 110})
        self.history = history
        self.feed = {"provider": "nba_stats_leagueseasonmatchups",
                     "observed_at_utc": "2026-11-10T18:00:00Z",
                     "games": {"g1": {"directions": [
                         {"off_team": "BOS", "def_team": "NYK", "status": "available", "rows": []},
                         {"off_team": "NYK", "def_team": "BOS", "status": "available", "rows": []}]}}}
        home_pairs = assign_by_position(self.home, self.away)
        away_pairs = assign_by_position(self.away, self.home)
        for direction, pairs, high in (("home", home_pairs, True), ("away", away_pairs, False)):
            target = self.feed["games"]["g1"]["directions"][0 if direction == "home" else 1]["rows"]
            defenders = self.away if direction == "home" else self.home
            for pair in pairs:
                off = pair["offense"]["player_id"]
                selected = pair["defense"]["player_id"]
                alternate = next(p["player_id"] for p in defenders if p["player_id"] != selected)
                selected_rate, alternate_rate = (0.8, 0.4) if high else (0.4, 0.8)
                target.extend([
                    {"off_player_id": off, "def_player_id": selected,
                     "partial_possessions": 25, "player_points": 25 * selected_rate},
                    {"off_player_id": off, "def_player_id": alternate,
                     "partial_possessions": 25, "player_points": 25 * alternate_rate},
                ])

    def test_pair_parser_normalizes_league_season_matchup_rows(self):
        row = _result_rows({"resultSets": [{"name": "SeasonMatchups",
            "headers": ["OFF_PLAYER_ID", "DEF_PLAYER_ID", "PARTIAL_POSS",
                        "PLAYER_PTS", "GP", "MATCHUP_MIN", "SEASON_ID"],
            "rowSet": [[1, 2, 12.5, 9, 3, "10:20", "22026"]]}]})
        self.assertEqual(row[0]["off_player_id"], "1")
        self.assertEqual(row[0]["partial_possessions"], 12.5)

    def test_pre_issue_head_to_head_evidence_changes_candidate_probability(self):
        result = build(self.snapshot, self.context, self.feed, self.history)
        row = result["games"][0]
        self.assertEqual(row["status"], "research_scenario")
        self.assertTrue(row["applied"])
        self.assertNotEqual(row["adjusted_home_probability"], row["base_home_probability"])
        self.assertFalse(row["assignments_verified"])

    def test_post_issue_matchup_capture_is_rejected(self):
        feed = json.loads(json.dumps(self.feed))
        feed["observed_at_utc"] = "2026-11-10T19:00:01Z"
        with self.assertRaisesRegex(ValueError, "after forecast issue"):
            build(self.snapshot, self.context, feed, self.history)

    def test_insufficient_exact_pairs_blocks_adjustment(self):
        feed = json.loads(json.dumps(self.feed))
        feed["games"]["g1"]["directions"][0]["rows"] = feed["games"]["g1"]["directions"][0]["rows"][:4]
        result = build(self.snapshot, self.context, feed, self.history)
        self.assertEqual(result["games"][0]["status"], "blocked")
        self.assertFalse(result["games"][0]["applied"])


if __name__ == "__main__":
    unittest.main()
