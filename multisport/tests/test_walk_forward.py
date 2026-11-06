import copy
import tempfile
import unittest
from multisport.walk_forward import walk_forward, snapshot, evaluate, elo_factory


def event(i, sport='nfl'):
    day = f'2025-01-{i:02}'
    return dict(event_id=str(i), sport=sport, market='home_win', season='2025',
                features={'rating': i}, outcome=i % 2, settled_at_utc=day+'T22:00:00Z',
                manifest=dict(prediction_as_of_utc=day+'T18:00:00Z', event_start_utc=day+'T20:00:00Z',
                              odds_used_in_model=False, sources=[dict(source_id='fixture', observed_at_utc=day+'T17:00:00Z', content_sha256='a'*64)]))


class WalkForwardTests(unittest.TestCase):
    def test_settlement_and_feature_isolation_all_sports(self):
        for sport in ('nba', 'nhl', 'nfl', 'soccer', 'tennis'):
            events = [event(i, sport) for i in range(1, 4)]
            events[0]['settled_at_utc'] = '2025-01-02T18:00:00Z'
            def factory(history, features):
                self.assertTrue(all(set(r) == {'features', 'outcome', 'season', 'event_id'} for r in history))
                return lambda features: .5
            rows = walk_forward(events, factory, ['rating'], {'without_rating': ['rating']})
            self.assertEqual(rows[1]['training_event_ids'], [])
            self.assertEqual(rows[2]['training_event_ids'], ['1', '2'])
            mutated = copy.deepcopy(events)
            mutated[-1]['outcome'] = 1-mutated[-1]['outcome']
            self.assertEqual(rows[-1]['probabilities'], walk_forward(mutated, factory, ['rating'])[-1]['probabilities'] | {'without_rating': .5})

    def test_future_source_and_duplicates_fail(self):
        e = event(1)
        with self.assertRaises(ValueError):
            walk_forward([e, e], None, ['rating'])
        e['manifest']['sources'][0]['observed_at_utc'] = '2025-01-01T19:00:00Z'
        with self.assertRaises(ValueError):
            walk_forward([e], None, ['rating'])

    def test_snapshots_cannot_overwrite(self):
        record = dict(event_id='1', model_version='v1', manifest=event(1)['manifest'], probabilities={'p': .6})
        with tempfile.TemporaryDirectory() as directory:
            snapshot(record, directory)
            record['probabilities']['p'] = .7
            with self.assertRaises(FileExistsError):
                snapshot(record, directory)

    def test_gate_and_metrics(self):
        rows = [dict(event_id=s+str(y), season=s, outcome=y, probabilities={'baseline': .5, 'challenger': .8 if y else .2, 'ablation': .6 if y else .4}) for s in ('2024', '2025') for y in (0, 1)]
        report = evaluate(rows, ['2024', '2025'], 2, ['ablation'])
        self.assertTrue(report['screening_passed'])
        self.assertFalse(report['automatic_promotion_allowed'])
        self.assertAlmostEqual(report['by_season']['2024']['challenger']['brier'], .04)
        self.assertEqual(sum(b['n'] for b in report['by_season']['2024']['challenger']['reliability_bins']), 2)
        self.assertFalse(evaluate(rows, ['2025'], 2)['screening_passed'])
        rows[-1]['probabilities']['challenger'] = .01
        self.assertFalse(evaluate(rows, ['2024', '2025'], 2, ['ablation'])['screening_passed'])

    def test_elo_baseline_learns_from_sports_results(self):
        history = [dict(features={'home_id': 'A', 'away_id': 'B'}, outcome=1)]
        predict = elo_factory(history, ['home_id', 'away_id'])
        self.assertGreater(predict({'home_id': 'A', 'away_id': 'B'}), .5)
        self.assertEqual(elo_factory([], ['home_id', 'away_id'])({'home_id': 'A', 'away_id': 'B'}), .5)

    def test_invalid_evaluation_cannot_pass_gate(self):
        row = dict(event_id='x', season='2025', outcome=1, probabilities={'baseline': .5, 'challenger': float('nan')})
        with self.assertRaises(ValueError): evaluate([row], ['2025'], 1)
        row['probabilities']['challenger'] = .9
        with self.assertRaises(ValueError): evaluate([row, row], ['2025'], 1)
