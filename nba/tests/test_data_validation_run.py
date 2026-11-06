"""Full-candidate gaps cannot be replaced by baseline retrospective scores."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_validation_run import candidate_assessment, observed_results, run
from test_postmortem_engine import build, inputs, seal, outcome


class DataValidationTests(unittest.TestCase):
    def test_no_forecasts_produces_no_calibration_or_hits(self):
        r=candidate_assessment([],[],['1','2'])
        self.assertEqual(r['historical_games_without_candidate_emission'],2)
        self.assertEqual(r['evaluation']['scored_ml_games'],0)
        for target in ('home_ml','away_ml','home_plus20','away_plus20'):
            m=r['evaluation']['metrics'][target]['challenger']
            self.assertEqual(m['n'],0)
            self.assertIsNone(m['brier'])
            self.assertIsNone(m['log_loss'])
        self.assertFalse(r['independent_validation_passed'])
        self.assertFalse(r['calibration_fit_performed'])

    def test_wrong_candidate_version_is_not_pooled(self):
        report=build(*inputs(),simulations=100)
        report['model_version']='NBA_CHALLENGER_2026_27_1_POSTMORTEM_V1'
        seal(report)
        with self.assertRaisesRegex(ValueError,'locked V2'):
            candidate_assessment([report],[outcome()],['future'])

    def test_replayed_forecast_cannot_become_prospective_metric(self):
        report=build(*inputs(),simulations=100)
        report['created_at_utc']='2026-11-07T00:00:00Z'
        report['emission_kind']='retrospective_replay'
        seal(report)
        with self.assertRaisesRegex(ValueError,'Post-start'):
            candidate_assessment([report],[outcome()],['future'])

    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError):run('unused','unused',d)

    def test_archived_observed_targets_have_no_probability_fields(self):
        root=Path(__file__).resolve().parents[2]
        rows=observed_results(root/'reports/nba-data-validation-2026-11-06/live-capture')
        self.assertEqual(len(rows),2)
        self.assertEqual([(r['home_max_lead'],r['away_max_lead']) for r in rows],[(30,6),(20,10)])
        self.assertTrue(all('prediction' not in r and 'p_home' not in r for r in rows))
        self.assertTrue(all(r['score_path_complete'] for r in rows))
