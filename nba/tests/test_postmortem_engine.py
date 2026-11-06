"""Synthetic arithmetic fixtures: no real player or predictive validation claims."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reproducible_slate import digest
from postmortem_engine import build as engine_build, save_new, team_projection, rotation_stints
from postmortem_backtest import evaluate
from score_path import lead_events, simulate, tilted_blocks
from possession_path_features import extract


CREATED = '2026-11-05T18:00:00Z'
TIP = '2026-11-06T00:00:00Z'


def build(*args, **kwargs):
    return engine_build(*args,emitted_at=CREATED,**kwargs)


def seal(value):
    value.pop('content_sha256',None)
    value['content_sha256'] = digest(value)
    return value


def source():
    return {'verified':True,'source_url':'https://example.org/synthetic-test-only',
            'source_sha256':'a'*64,'available_at_utc':'2026-11-05T17:00:00Z',
            'observed_at_utc':'2026-11-05T17:30:00Z'}


def team(prefix='p'):
    return {'roster_complete':True, 'confirmed_starters':[prefix+str(i) for i in range(5)],
            **{k:source() for k in ('roster_evidence','injury_evidence','lineup_evidence','metrics_evidence','schedule_evidence')},
            'metrics_through_utc':'2026-11-04T12:00:00Z',
            'target_tipoff_utc':TIP,
            'schedule':{'previous_tipoff_utc':'2026-11-03T00:00:00Z',
                        'previous_completed_at_utc':'2026-11-03T03:00:00Z',
                        'previous_overtime_periods':0},
            'players':[{'player_id':prefix+str(i),'status':'available','baseline_minutes':24,
                        'max_minutes':40,'baseline_usage':.2,'max_usage':.4,
                        'offense_on_off':8-i,'defense_on_off':i-8,'on_off_possessions':2000,
                        'replacement_quality':1.5-i/10,'turnover_on_off':.002*i,'forced_turnover_on_off':.002*i,
                        'minutes_last_48h':0,
                        'roles':{'creation':.5,'spacing':.5,'rim':.5,'rebounding':.5}}
                       for i in range(10)],
            'turnover_adjustment_method':'opponent_residual_v1',
            'pace_regulation':100,'turnover_rate':.14,'forced_turnover_rate':.14,
            'transition_bonus':.15,'path_sample_possessions':400,
            'non_turnover_blocks':[[0,0,0,0],[0,2,0,2],[2,3,2,3],[3,3,3,3]]}


def inputs():
    game = {'game_id':'future','home_team':'H','away_team':'A','tipoff_utc':TIP,
            'elo_p_home':.55,'challenger_p_home':.54,'hybrid_p_home':.545}
    snapshot = seal({'created_at_utc':CREATED,'predictions':[game]})
    evidence = {'snapshot_sha256':snapshot['content_sha256'],
                'games':{'future':{'teams':{'H':team(),'A':team('q')}}}}
    boxes = {'games':[]}
    for i in range(6):
        boxes['games'].append({'game':{'game_id':str(i),'home_team':'H','away_team':'A',
                                       'tipoff_utc':'2026-10-%02dT00:00:00Z' % (10+i),
                                       'home_points':110,'away_points':110},
                               'observed_at_utc':'2026-10-%02dT04:00:00Z' % (10+i),
                               'team_statistics':{'H':{'points':110,'possessions_estimated':100},
                                                  'A':{'points':110,'possessions_estimated':100}}})
    return snapshot,evidence,boxes


def outcome():
    return {'game_id':'future','home_team':'H','away_team':'A','tipoff_utc':TIP,
            'completed_at_utc':'2026-11-06T03:00:00Z','home_points':111,'away_points':115,
            'score_path_complete':True,'home_max_lead':22,'away_max_lead':24,
            'evidence':{**source(),'available_at_utc':'2026-11-06T03:00:00Z',
                        'observed_at_utc':'2026-11-06T04:00:00Z'}}


class PostmortemTests(unittest.TestCase):
    def test_projected_and_unknown_lineups_generate_two_sided_research(self):
        from nba.daily_pipeline import sporting_report
        s,e,b = inputs()
        home = e['games']['future']['teams']['H']
        home['projected_starters'] = home.pop('confirmed_starters')
        away = e['games']['future']['teams']['A']
        away.pop('confirmed_starters')
        away.pop('lineup_evidence')
        r, summary = sporting_report(s,e,b,simulations=100,emitted_at=CREATED)
        game = r['games'][0]
        self.assertIsNotNone(game['challenger'])
        self.assertEqual(game['lineup_context']['H']['status'],'projected')
        self.assertEqual(game['lineup_context']['A']['status'],'unknown')
        self.assertEqual(summary['integrated_research_games'],1)
        self.assertTrue({'home_ml','away_ml','home_plus20','away_plus20'} <=
                        set(game['challenger']['path']['probabilities']))
        self.assertFalse(summary['production_approved'])

    def test_projected_absent_starter_and_future_source_rejected(self):
        for failure in ('out','future'):
            s,e,b = inputs()
            home = e['games']['future']['teams']['H']
            home['projected_starters'] = home.pop('confirmed_starters')
            if failure == 'out':home['players'][0]['status']='out'
            else:home['lineup_evidence']['observed_at_utc']=TIP
            self.assertIsNone(build(s,e,b,simulations=50)['games'][0]['challenger'])

    def test_daily_summary_discloses_empty_integration(self):
        from nba.daily_pipeline import sporting_report
        s,e,b = inputs()
        r, summary = sporting_report(s,simulations=50,emitted_at=CREATED)
        self.assertEqual(summary['integrated_research_games'],0)
        self.assertIn('Missing verified roster',summary['game_diagnostics'][0]['missing'][0])

    def test_full_game_two_sided_and_sealed(self):
        args = inputs()
        report = build(*args,simulations=100)
        g = report['games'][0]
        self.assertIsNotNone(g['challenger'])
        self.assertEqual(set(g['challenger']['teams']),{'H','A'})
        self.assertEqual(g['recommendation'],'PASS')
        self.assertFalse(g['eligible_for_bet'])
        self.assertIsNone(g['final_probabilities'])
        args[1]['games'].clear()
        self.assertTrue(report['inputs']['evidence']['games'])

    def test_every_game_and_missing_either_side_pass(self):
        s,e,b = inputs()
        g = dict(s['predictions'][0],game_id='second')
        s['predictions'].append(g)
        seal(s)
        e['snapshot_sha256'] = s['content_sha256']
        e['games']['future']['teams'].pop('A')
        report = build(s,e,b,simulations=100)
        self.assertEqual(len(report['games']),2)
        self.assertTrue(all(g['challenger'] is None for g in report['games']))
        self.assertTrue(all(g['recommendation'] == 'PASS' for g in report['games']))

    def test_minutes_usage_and_all_bench_members(self):
        t = team()
        t['players'][0]['status'] = 'out'
        t['players'][1]['status'] = 'out'
        r = team_projection(t,{})
        self.assertEqual(len(r['players']),10)
        self.assertAlmostEqual(sum(p['minutes'] for p in r['players']),240,places=4)
        self.assertAlmostEqual(sum(p['team_possession_share'] for p in r['players']),1,places=4)
        self.assertTrue(all(p['minutes'] == 0 for p in r['players'][:2]))
        self.assertTrue(all(p['usage'] <= .4001 for p in r['players']))
        self.assertNotEqual(r['players'][2]['minutes'],r['players'][9]['minutes'])
        realized = {p['player_id']:0 for p in r['players']}
        for stint in r['rotation_stints']:
            self.assertEqual(len(set(stint['players'])),5)
            for pid in stint['players']:
                realized[pid] += stint['minutes']
        for p in r['players']:
            self.assertAlmostEqual(realized[p['player_id']],p['minutes'],places=4)

    def test_quality_changes_injury_effect(self):
        t = team()
        t['players'][0]['status'] = 'out'
        before = team_projection(t,{})
        t['players'][9]['replacement_quality'] = 3
        after = team_projection(t,{})
        self.assertGreater(after['players'][9]['minutes'],before['players'][9]['minutes'])
        self.assertLess(after['offense_delta_per_100'],before['offense_delta_per_100'])

    def test_nonlinear_joint_absence_and_usage(self):
        t = team()
        # Remaining players cannot reproduce missing role quality.
        for p in t['players'][2:]:
            p['roles']['spacing'] = .05
        one = team_projection(t,{'p0':'out'})
        two = team_projection(t,{'p0':'out','p1':'out'})
        self.assertGreater(two['nonlinear_joint_penalty_per_100'],2*one['nonlinear_joint_penalty_per_100'])

    def test_joint_questionable_scenarios_no_guessed_weights(self):
        s,e,b = inputs()
        for t in ('H','A'):
            e['games']['future']['teams'][t]['players'][7]['status'] = 'questionable'
        g = build(s,e,b,simulations=100)['games'][0]
        self.assertIsNone(g['challenger'])
        self.assertEqual(len(g['on_off_scenarios']),4)
        self.assertTrue(all(x['scenario_weight'] is None for x in g['on_off_scenarios']))
        self.assertTrue(all(x['forecast'] is not None for x in g['on_off_scenarios']))

    def test_bad_material_data_blocks(self):
        mutations = [lambda t:t['injury_evidence'].update(verified=False),
                     lambda t:t['metrics_evidence'].update(observed_at_utc='2026-11-06T01:00:00Z'),
                     lambda t:t['players'][0].update(status='unknown'),
                     lambda t:t['players'][0].update(offense_on_off=float('nan')),
                     lambda t:t['players'][0].update(max_minutes=49),
                     lambda t:t.update(roster_complete=False),
                     lambda t:t.update(non_turnover_blocks=[])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                s,e,b = inputs()
                mutate(e['games']['future']['teams']['A'])
                if math_is_nan(e):
                    # Nonfinite source data cannot be frozen into JSON.
                    with self.assertRaises(ValueError):build(s,e,b,simulations=100)
                else:
                    self.assertIsNone(build(s,e,b,simulations=100)['games'][0]['challenger'])

    def test_market_inputs_and_hash_tampering_rejected(self):
        s,e,b = inputs()
        e['games']['future']['teams']['H']['bookmaker_odds'] = 1.9
        with self.assertRaises(ValueError):build(s,e,b,simulations=100)
        s,e,b = inputs()
        s['predictions'][0]['elo_p_home'] = .8
        with self.assertRaises(ValueError):build(s,e,b,simulations=100)

    def test_player_cannot_be_on_both_rosters(self):
        s,e,b = inputs()
        e['games']['future']['teams']['A'] = team()
        report = build(s,e,b,simulations=100)
        self.assertIsNone(report['games'][0]['challenger'])
        self.assertIn('both opponents',report['games'][0]['missing'][0])

    def test_create_only_and_backtest_tamper_check(self):
        report = build(*inputs(),simulations=100)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'snapshot.json'
            save_new(path,report)
            with self.assertRaises(FileExistsError):save_new(path,report)
            self.assertEqual(json.loads(path.read_text())['content_sha256'],report['content_sha256'])
        report['games'][0]['challenger']['path']['probabilities']['home_ml'] = .99
        with self.assertRaises(ValueError):evaluate([report],[outcome()])

    def test_chronological_paired_scores_and_path_labels(self):
        report = build(*inputs(),simulations=100)
        scored = evaluate([report],[outcome()])
        self.assertEqual(scored['scored_ml_games'],1)
        self.assertEqual(scored['metrics']['home_plus20']['challenger']['n'],1)
        self.assertEqual(scored['chronological_games'][0]['home_plus20_outcome'],1)
        self.assertEqual(scored['chronological_games'][0]['home_ml_outcome'],0)
        self.assertFalse(scored['independent_holdout_validation_passed'])
        with self.assertRaises(ValueError):evaluate([report,report],[outcome()])

    def test_final_margin_never_substitutes_for_missing_path(self):
        report = build(*inputs(),simulations=100)
        result = outcome()
        result['score_path_complete'] = False
        result.pop('home_max_lead')
        result.pop('away_max_lead')
        scored = evaluate([report],[result])
        self.assertEqual(scored['scored_ml_games'],1)
        self.assertEqual(scored['metrics']['home_plus20']['challenger']['n'],0)

    def test_turnover_pressure_moves_projection(self):
        s,e,b = inputs()
        before = build(s,e,b,simulations=100)['games'][0]['challenger']
        e['games']['future']['teams']['A']['forced_turnover_rate'] = .3
        after = build(s,e,b,simulations=100)['games'][0]['challenger']
        self.assertGreater(after['projections']['H']['expected_turnovers'],before['projections']['H']['expected_turnovers'])
        self.assertLess(after['projections']['H']['ppp'],before['projections']['H']['ppp'])

    def test_all_30_teams_including_knicks_use_same_gate(self):
        s,e,b = inputs()
        s['predictions'] = []
        e['games'] = {}
        for i in range(15):
            s['predictions'].append({'game_id':str(i),'home_team':'NYK' if i == 0 else 'T'+str(2*i),
                                    'away_team':'T'+str(2*i+1),'tipoff_utc':TIP,
                                    'elo_p_home':.5,'challenger_p_home':.5,'hybrid_p_home':.5})
        seal(s)
        e['snapshot_sha256'] = s['content_sha256']
        report = build(s,e,b,simulations=100)
        self.assertEqual(len(report['games']),15)
        self.assertTrue(all(g['recommendation'] == 'PASS' for g in report['games']))

    def test_replay_does_not_backdate_emission(self):
        report = engine_build(*inputs(),simulations=100,emitted_at='2026-11-07T00:00:00Z')
        self.assertEqual(report['emission_kind'],'retrospective_replay')
        self.assertEqual(report['prediction_as_of_utc'],CREATED)
        with self.assertRaises(ValueError):evaluate([report],[outcome()])
        with self.assertRaises(ValueError):
            engine_build(*inputs(),emitted_at='2026-11-05T16:00:00Z')


def math_is_nan(value):
    return 'NaN' in json.dumps(value)


class ScorePathTests(unittest.TestCase):
    def test_reach20_is_not_final_margin_or_complement(self):
        events = [(0,3)]*7 + [(1,3)]*15 + [(0,3)]*7
        h,a,mh,ma = lead_events(events)
        self.assertLess(h,a)
        self.assertLess(abs(h-a),20)
        self.assertGreaterEqual(mh,20)
        self.assertGreaterEqual(ma,20)

    def test_simulation_deterministic_complement_and_union(self):
        t = {'ppp':1.1,'turnover_rate':.14,'transition_bonus':.15,
             'non_turnover_blocks':team()['non_turnover_blocks']}
        a = simulate(t,t,100,simulations=500)
        self.assertEqual(a,simulate(t,t,100,simulations=500))
        p = a['probabilities']
        self.assertAlmostEqual(p['home_ml']+p['away_ml'],1)
        self.assertAlmostEqual(p['home_plus20']+p['away_plus20']-p['both_plus20'],p['either_plus20'])
        self.assertLess(abs(p['home_ml']-.5),.1)
        self.assertTrue(a['includes_overtime'])
        self.assertGreater(a['overtime_games'],0)

    def test_scoring_runs_change_plus20_at_equal_expected_ppp(self):
        common = {'ppp':1.1,'turnover_rate':.14,'transition_bonus':0}
        burst = {**common,'non_turnover_blocks':[[0,0,0,0],[3,3,3,3],[2,2,2,2]]}
        mixed = {**common,'non_turnover_blocks':[[0,0,0,2],[0,2,0,3],[2,3,2,3]]}
        a = simulate(burst,burst,100,simulations=2000)
        b = simulate(mixed,mixed,100,simulations=2000)
        self.assertGreater(a['probabilities']['either_plus20'],b['probabilities']['either_plus20'])
        self.assertLess(abs(a['probabilities']['home_ml']-.5),.06)
        self.assertLess(abs(b['probabilities']['home_ml']-.5),.06)

    def test_empirical_support_and_nonfinite_inputs(self):
        with self.assertRaises(ValueError):tilted_blocks([[0]*4]*3,1)
        with self.assertRaises(ValueError):tilted_blocks([[float('nan')]*4]*3,1)
        with self.assertRaises(ValueError):simulate({}, {},100,simulations=0)


class PossessionExtractionTests(unittest.TestCase):
    def archive(self):
        games = []
        for i in range(3):
            events = []
            for j in range(100):
                for side in ('H','A'):
                    to = j%7 == (0 if side == 'H' else 3)
                    events.append({'sequence':len(events),'team':side,'turnover':to,
                                   'points':0 if to else (3 if j%3 == 0 else 1)})
            scores = {t:sum(e['points'] for e in events if e['team'] == t) for t in ('H','A')}
            # Ensure a non-tied final without changing possession semantics.
            last = events[-1]
            last['points'] += 1
            scores['A'] += 1
            games.append({'game_id':str(i),'tipoff_utc':'2026-10-%02dT00:00:00Z'%(10+i),
                          'completed_at_utc':'2026-10-%02dT03:00:00Z'%(10+i),
                          'home_team':'H','away_team':'A','home_points':scores['H'],'away_points':scores['A'],
                          'duration_minutes':48,'complete':True,'possessions':events,'evidence':source()})
        return {'games':games}

    def test_real_units_and_score_reconciliation(self):
        report = extract(self.archive(),CREATED,TIP)
        for t in ('H','A'):
            self.assertEqual(report['teams'][t]['status'],'research_features_only')
            self.assertEqual(report['teams'][t]['pace_regulation'],100)
            self.assertEqual(report['teams'][t]['path_sample_possessions'],300)
            self.assertGreater(report['teams'][t]['turnover_rate'],0)
            feature = report['teams'][t]
            self.assertEqual(feature['turnover_adjustment_method'],'opponent_residual_v1')
            archive = self.archive()
            league = sum(e['turnover'] for g in archive['games'] for e in g['possessions'])/sum(len(g['possessions']) for g in archive['games'])
            self.assertAlmostEqual(feature['turnover_rate'],league+feature['raw_turnover_rate']-feature['opponent_expected_forced_rate'])

    def test_partial_future_duplicate_and_score_mismatch_rejected(self):
        for field,value in [('complete',False),('home_points',999),('completed_at_utc',TIP)]:
            archive = self.archive()
            archive['games'][0][field] = value
            with self.assertRaises(ValueError):extract(archive,CREATED,TIP)
        archive = self.archive()
        archive['games'].append(copy.deepcopy(archive['games'][0]))
        with self.assertRaises(ValueError):extract(archive,CREATED,TIP)


if __name__ == '__main__':
    unittest.main()
