import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livedata_forward_evaluation import VERSION, evaluate
from reproducible_slate import digest


class EvaluationTests(unittest.TestCase):
    def test_scores_earliest_pregame_pair_only_and_excludes_mismatched_result(self):
        tip = '2026-11-09T22:00:00Z'

        def report(hour, home_ml):
            result = {'model_version': VERSION, 'emitted_at_utc': f'2026-11-09T{hour}:00:00Z',
                      'games': [{'game_id': 'one', 'tipoff_utc': tip, 'home_team': 'GS',
                                 'away_team': 'WSH', 'base_home_ml': .6, 'home_ml': home_ml,
                                 'status': 'research_team_ml'}]}
            return {**result, 'content_sha256': digest(result)}

        final = {'id': 'one', 'sport': 'nba', 'status': 'STATUS_FINAL', 'completed': True,
                 'start_utc': tip, 'home': 'Golden State Warriors', 'away': 'Washington Wizards',
                 'home_score': '110', 'away_score': '100'}
        reports = [report('22', .99), report('21', .8), report('20', .7)]
        cutoff = '2026-11-10T03:00:00Z'
        summary = evaluate(reports, [final], cutoff)
        self.assertEqual(len(summary['scored_games']), 1)
        self.assertEqual(summary['scored_games'][0]['livedata_home'], .7)
        self.assertAlmostEqual(summary['delta_livedata_minus_hybrid']['brier'], -.07)
        summary = evaluate(reports, [dict(final, away='Boston Celtics')], cutoff)
        self.assertEqual(len(summary['result_errors']), 1)
        self.assertIsNone(summary['metrics']['livedata']['log_loss'])
