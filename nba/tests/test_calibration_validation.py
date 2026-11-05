import json
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibration_validation import calibration,paired_bootstrap,wilson,prediction_rows,evaluate_history

class CalibrationValidationTests(unittest.TestCase):
    def test_hand_computed_calibration(self):
        r=calibration([(.25,0),(.75,1)])
        self.assertEqual(r['brier'],.0625)
        self.assertAlmostEqual(r['log_loss'],-math.log(.75))
        self.assertEqual(r['mean_bias'],0)
        self.assertEqual(r['ece_10_equal_width'],.25)
        self.assertEqual(sum(b['n'] for b in r['reliability_bins']),2)
        self.assertIsNone(r['reliability_bins'][0]['observed_rate'])
        self.assertFalse(r['calibrated_certified'])

    def test_wilson_boundary(self):
        self.assertIsNone(wilson(0,0))
        lo,hi=wilson(0,10)
        self.assertAlmostEqual(lo,0)
        self.assertAlmostEqual(hi,.2775327998628892)

    def test_identical_paired_models_have_zero_uncertainty(self):
        rows=[{'league_date':f'2026-01-{i:02d}','season':2026,'elo':.6,'challenger':.6,'y':i%2} for i in range(1,20)]
        r=paired_bootstrap(rows,100,unit='week')
        self.assertEqual(r['brier']['percentile95'],[0,0])
        self.assertEqual(r['log_loss']['percentile95'],[0,0])
        self.assertEqual(r,paired_bootstrap(rows,100,unit='week'))

    def test_constant_known_improvement_retains_cluster_pairing(self):
        rows=[{'league_date':f'2026-01-{i:02d}','season':2026,'elo':.5,'challenger':.8,'y':1} for i in range(1,20)]
        for unit in ('day','week'):
            r=paired_bootstrap(rows,100,unit=unit)
            self.assertAlmostEqual(r['brier']['gain_elo_minus_challenger'],.21)
            for bound in r['brier']['percentile95']:self.assertAlmostEqual(bound,.21)

    def test_invalid_probabilities_and_empty_input(self):
        for p in (0,1,True,float('nan')):
            with self.assertRaises(ValueError):calibration([(p,1)])
        with self.assertRaises(ValueError):calibration([])
        with self.assertRaises(ValueError):paired_bootstrap([],100)
        with self.assertRaises(ValueError):prediction_rows([])

    def test_validation_manifest_and_frozen_protocol(self):
        import hashlib
        root=Path(__file__).resolve().parents[2]
        folder=root/'reports/nba-validation-2026-11-04'
        manifest=json.loads((folder/'manifest.json').read_text())
        for name,expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),expected)
        protocol=json.loads((folder/'prospective_protocol.json').read_text())
        self.assertLess(protocol['registered_at_utc'],protocol['forecast_window_start_utc'])
        for name,expected in protocol['locked_model_source_sha256'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected)
        self.assertFalse(protocol['independent_validation_passed'])
        self.assertFalse(protocol['automatic_promotion_allowed'])

    def test_archive_replay_with_cross_platform_float_tolerance(self):
        root=Path(__file__).resolve().parents[2]
        history=[g for g in json.loads((root/'reports/nba-2026-11-04/history.json').read_text()) if g['season']!=2027]
        expected=json.loads((root/'reports/nba-validation-2026-11-04/calibration.json').read_text())
        actual=evaluate_history(history)
        self.assertEqual(actual['scored_games'],2460)
        self.assertFalse(actual['independent_validation_passed'])
        for label,g in expected['groups'].items():
            for model in ('elo','challenger'):
                for key in ('brier','log_loss','mean_bias','ece_10_equal_width'):
                    self.assertAlmostEqual(actual['groups'][label][model][key],g[model][key],delta=1e-12)
            for unit in ('day','week'):
                for metric in ('brier','log_loss'):
                    for x,y in zip(actual['groups'][label]['paired_uncertainty'][unit][metric]['percentile95'],g['paired_uncertainty'][unit][metric]['percentile95']):
                        self.assertAlmostEqual(x,y,delta=1e-12)

if __name__=='__main__':unittest.main()
