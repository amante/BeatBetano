import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import multisport.forecast_revisions as revisions
from multisport.data_lineage import digest
from multisport.forecast_evaluation import evaluate
from multisport.sport_adapters import adapt


class FrozenDateTime(datetime):
    instant = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        value = cls.instant
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def source(sport, event_id, home, away, start, as_of, probability, model="test-model"):
    event = {
        "event_id": event_id, "game_id": event_id, "start_utc": start,
        "home": home, "away": away, "model_version": model,
        "forecast_probabilities": {"home": probability, "away": 1-probability},
        "assumptions": ["Test baseline"], "unresolved_inputs": [],
    }
    key = "predictions" if sport == "nba" else "games" if sport == "nhl" else "events"
    return {"as_of_utc": as_of, "odds_used": False, key: [event]}


def frozen_snapshot(sport, data, stage="initial", previous=None, instant=None):
    old = FrozenDateTime.instant
    FrozenDateTime.instant = instant or old
    try:
        with patch.object(revisions, "datetime", FrozenDateTime):
            return revisions.snapshot(adapt(sport, data, stage=stage), previous)
    finally:
        FrozenDateTime.instant = old


class ForecastEvaluationTests(unittest.TestCase):
    def write_chain(self, root, sport, event_id, snapshots):
        folder = Path(root) / sport / digest(event_id)
        folder.mkdir(parents=True)
        for index, snap in enumerate(snapshots, 1):
            (folder / f"{index:06d}.json").write_text(json.dumps(snap))

    def test_scores_only_latest_pregame_emission_once_per_model_version(self):
        start = "2026-11-07T18:00:00Z"
        first = frozen_snapshot(
            "nba", source("nba", "evt-1", "BOS", "MIL", start,
                          "2026-11-07T10:00:00Z", .55),
            instant=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc),
        )
        second = frozen_snapshot(
            "nba", source("nba", "evt-1", "BOS", "MIL", start,
                          "2026-11-07T13:00:00Z", .60),
            stage="update", previous=first,
            instant=datetime(2026, 11, 7, 14, 0, tzinfo=timezone.utc),
        )
        history = [{
            "id": "evt-1", "source_event_id": "evt-1", "sport": "nba",
            "home": "Boston Celtics", "away": "Milwaukee Bucks",
            "start_utc": start, "status": "STATUS_FINAL", "completed": True,
            "home_score": "110", "away_score": "100", "source": "test feed",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            self.write_chain(tmp, "nba", "evt-1", [first, second])
            report = evaluate(tmp, history)
        self.assertEqual(report["coverage"]["scored_forecast_groups"], 1)
        self.assertEqual(report["groups"][0]["stage"], "update")
        metrics = report["groups"][0]["metrics"]
        self.assertEqual(metrics["n"], 1)
        self.assertAlmostEqual(metrics["brier"], .16)
        self.assertAlmostEqual(metrics["log_loss"], -__import__("math").log(.60))
        self.assertFalse(report["certification"]["certified"])
        self.assertFalse(report["certification"]["automatic_promotion_allowed"])

    def test_nhl_binding_requires_team_order_and_exact_start(self):
        start = "2026-11-07T18:00:00Z"
        snap = frozen_snapshot(
            "nhl", source("nhl", "nhl-event", "BOS", "MTL", start,
                          "2026-11-07T10:00:00Z", .60),
            instant=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc),
        )
        history = [{
            "id": "espn-event", "source_event_id": "espn-event", "sport": "nhl",
            "home": "Boston Bruins", "away": "Montreal Canadiens",
            "start_utc": start, "status": "STATUS_FINAL", "completed": True,
            "home_score": "4", "away_score": "2", "source": "test feed",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            self.write_chain(tmp, "nhl", "nhl-event", [snap])
            report = evaluate(tmp, history)
        self.assertEqual(report["coverage"]["forecasts_bound_to_history"], 1)
        self.assertEqual(report["coverage"]["scored_forecast_groups"], 1)

    def test_tennis_score_is_not_guessed_from_raw_score_fields(self):
        start = "2026-11-07T18:00:00Z"
        snap = frozen_snapshot(
            "tennis", source("tennis", "1", "Player A", "Player B", start,
                             "2026-11-07T10:00:00Z", .60),
            instant=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc),
        )
        history = [{
            "id": "1", "source_event_id": "1", "sport": "tennis",
            "home": "Player A", "away": "Player B", "start_utc": start,
            "status": "STATUS_FINAL", "completed": True,
            "home_score": "2", "away_score": "0", "source": "test feed",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            self.write_chain(tmp, "tennis", "1", [snap])
            report = evaluate(tmp, history)
        self.assertFalse(report["groups"])
        self.assertEqual(report["exclusion_counts"]["sport_specific_winner_not_available"], 1)
        self.assertFalse(report["certification"]["certified"])


if __name__ == "__main__":
    unittest.main()
