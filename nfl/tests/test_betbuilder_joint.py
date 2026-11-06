import copy
import random
import unittest
from nfl.betbuilder_joint import simulate, draw, historical_audit


def config():
    players = []
    for team in ('A', 'B'):
        for pos in ('QB', 'WR', 'TE', 'RB', 'DEF'):
            players.append(dict(player_id=team+pos, team=team, position=pos,
                status='available', snap_share=1, catch_rate=.8, explosive_rate=.06,
                target_weight=1 if pos in ('WR', 'TE', 'RB') else 0,
                carry_weight=1 if pos == 'RB' else 0,
                tackle_weight=1 if pos == 'DEF' else 0,
                yards_per_catch=12, yards_per_carry=4))
    return dict(teams=['A', 'B'], players=players,
        manifest=dict(prediction_as_of_utc='2025-01-01T18:00:00Z', event_start_utc='2025-01-01T20:00:00Z', odds_used_in_model=False,
            sources=[dict(source_id='synthetic', observed_at_utc='2025-01-01T17:00:00Z', content_sha256='a'*64)]),
        scenarios=[dict(weight=.5, game_script='A trails', pace_factor=1.1, weather_factor=1,
             tackle_probability=.7, plays={'A': 65, 'B': 60}, pass_rate={'A': .8, 'B': .4}),
             dict(weight=.5, game_script='A leads', pace_factor=.9, weather_factor=.8,
             tackle_probability=.7, plays={'A': 60, 'B': 65}, pass_rate={'A': .4, 'B': .8})])


def leg(player='AWR', market='receiving_yards', value=50, op='ge'):
    return dict(player_id=player, market=market, value=value, op=op)


class JointTests(unittest.TestCase):
    def test_conservation_and_binary_event(self):
        c = config()
        for i in range(40):
            stats = draw(c, random.Random(i))
            for team in c['teams']:
                self.assertAlmostEqual(stats[team+'QB']['pass_yards'], sum(stats[team+p]['receiving_yards'] for p in ('WR', 'TE', 'RB')))
                for pos in ('WR', 'TE', 'RB'):
                    x = stats[team+pos]
                    self.assertLessEqual(x['receptions'], x['targets'])
                    self.assertLessEqual(x['targets']+x['carries'], x['snaps'])
                    self.assertIs(type(x['longest_reception_50_plus']), bool)
                    if x['longest_reception_50_plus']:
                        self.assertGreaterEqual(x['receiving_yards'], 50)
                self.assertLessEqual(stats[team+'DEF']['tackles'], stats[team+'DEF']['snaps'])

    def test_nested_legs_break_independence(self):
        c = config()
        result = simulate(c, [leg(value=40), leg(value=80)], 2000)
        self.assertEqual(result['joint_probability'], result['marginal_probabilities'][1])
        self.assertGreater(result['joint_minus_independence'], .01)
        self.assertEqual(result, simulate(c, [leg(value=40), leg(value=80)], 2000))

    def test_13_legs_and_zero_hits_uncertainty(self):
        legs = [leg(value=i*10) for i in range(1, 14)]
        result = simulate(config(), legs, 100)
        self.assertEqual(sum(result['hit_patterns'].values()), 100)
        self.assertLessEqual(result['joint_probability'], min(result['marginal_probabilities']))
        zero = simulate(config(), [leg(value=100000)], 100)
        self.assertEqual(zero['joint_probability'], 0)
        self.assertGreater(zero['joint_mc_interval95'][1], 0)
        with self.assertRaises(ValueError):
            simulate(config(), legs+[leg(value=200)], 100)

    def test_binary_is_strict_and_contradictions_zero(self):
        with self.assertRaises(ValueError):
            simulate(config(), [leg(market='longest_reception_50_plus', value=50)], 100)
        result = simulate(config(), [leg(market='longest_reception_50_plus', value=True, op='is'), leg(market='longest_reception_50_plus', value=False, op='is')], 100)
        self.assertEqual(result['joint_probability'], 0)

    def test_bad_inputs_and_out_player(self):
        c = config()
        c['players'][1]['status'] = 'out'
        result = simulate(c, [leg(market='receptions', value=1)], 100)
        self.assertEqual(result['joint_probability'], 0)
        for mutation in ('weights', 'future', 'nan', 'availability'):
            bad = config()
            if mutation == 'weights': bad['scenarios'][0]['weight'] = .9
            if mutation == 'future': bad['manifest']['prediction_as_of_utc'] = '2025-01-01T21:00:00Z'
            if mutation == 'nan': bad['players'][0]['snap_share'] = float('nan')
            if mutation == 'availability': bad['players'][0]['status'] = 'questionable'
            with self.assertRaises(ValueError): simulate(bad, [leg()], 100)

    def test_historical_scoring_and_leakage(self):
        rows = [dict(event_id=str(i), builder_id='builder', season=str(i), manifest=config()['manifest'],
                     training_cutoff_utc='2024-01-01T00:00:00Z', settled_at_utc='2025-01-02T00:00:00Z',
                     outcome=1, joint_probability=.8, independence_probability=.5) for i in (1, 2)]
        report = historical_audit(rows)
        self.assertAlmostEqual(report['by_season']['1']['joint_probability']['brier'], .04)
        self.assertFalse(report['calibrated'])
        rows[0]['training_cutoff_utc'] = '2026-01-01T00:00:00Z'
        with self.assertRaises(ValueError): historical_audit(rows)
