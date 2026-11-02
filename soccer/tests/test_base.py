import unittest
from soccer.data import normalize
from soccer.poisson import fit, predict, goal_distribution, frequency, metrics


class FootballBaseTests(unittest.TestCase):
    def test_score_formats_and_no_halftime_fallback(self):
        base = dict(date='2025-01-01', team1='A', team2='B')
        for score in ([2, 1], {'ft': [2, 1]}):
            self.assertEqual(normalize({'matches': [dict(base, score=score)]}, 'x')[0]['hg'], 2)
        self.assertEqual(normalize({'matches': [dict(base, score={'ht': [1, 0]})]}, 'x'), [])
        with self.assertRaises(ValueError): normalize({'matches': [dict(base, score=[True, 0])]}, 'x')
        with self.assertRaises(ValueError): normalize({'matches': [dict(base, score=[1, 0])]*2}, 'x')

    def test_symmetric_rates_draw_and_tail(self):
        model = dict(teams={'A': 0, 'B': 1}, coefficients=[0.]*6, trained_through='2024-01-01')
        p = predict(model, 'A', 'B', '2024-01-02')
        self.assertAlmostEqual(p['probabilities'][0], p['probabilities'][2])
        self.assertGreater(p['probabilities'][1], .3)
        self.assertAlmostEqual(sum(p['probabilities']), 1.)
        self.assertLess(p['omitted_mass'], 1e-8)
        self.assertAlmostEqual(sum(i*q for i,q in enumerate(goal_distribution(3))), 3., places=7)
        with self.assertRaises(ValueError): predict(model, 'A', 'B', '2024-01-01')
        self.assertEqual(predict(model, 'C', 'B', '2024-01-02')['unknown_teams'], ['C'])

    def test_fit_home_advantage_and_identifiability(self):
        rows = [dict(home=h, away=a, hg=2, ag=1, date='2024-01-01') for h,a in [('A','B'),('B','A')]]*20
        model = fit(rows)
        p = predict(model, 'A', 'B', '2024-01-02')
        self.assertGreater(p['probabilities'][0], p['probabilities'][2])
        self.assertAlmostEqual(p['expected_goals'][0], 2., places=4)
        self.assertAlmostEqual(sum(model['coefficients'][2:4]), 0.)
        with self.assertRaises(RuntimeError): fit(rows, iterations=0)

    def test_multiclass_metric_definition(self):
        rows = [dict(hg=0, ag=0)]
        score = metrics([[.2, .5, .3]], rows)
        self.assertAlmostEqual(score['brier_sum'], .38)
        self.assertEqual(score['accuracy'], 1.)
        self.assertAlmostEqual(sum(frequency(rows)), 1.)
        with self.assertRaises(ValueError): metrics([], rows)


if __name__ == '__main__': unittest.main()

class HistoricalCoverageTests(unittest.TestCase):
    def test_committed_history_is_complete_and_chronological(self):
        from pathlib import Path
        from soccer.data import load_history
        rows, manifest = load_history(Path(__file__).resolve().parents[2] / 'reports/soccer/base-2026-11-02/history')
        self.assertEqual(len(rows), 1900)
        self.assertEqual([m['games'] for m in manifest], [380]*5)
        for previous, following in zip(manifest, manifest[1:]):
            self.assertLess(max(r['date'] for r in rows if r['season']==previous['season']), min(r['date'] for r in rows if r['season']==following['season']))
