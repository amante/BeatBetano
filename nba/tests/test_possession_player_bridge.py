"""Synthetic regression/ingestion checks; no real predictive validation claims."""
import copy
import json
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_postmortem_engine as legacy
inputs,source,CREATED,TIP = legacy.inputs,legacy.source,legacy.CREATED,legacy.TIP
from player_possession_effects import fit, ridge
from possession_player_bridge import connect
from postmortem_engine import build, player_effect_values, verify_seal


def archive():
    data=legacy.PossessionExtractionTests().archive()
    data['evidence']=source()
    for g in data['games']:
        g['team_rosters']={t:[prefix+str(i) for i in range(10)] for t,prefix in (('H','p'),('A','q'))}
        g['lineup_evidence']=source()
        g['lineup_attribution']='possession_start'
        for event in g['possessions']:
            # Five distinct players; alternating groups give each player on and off exposure.
            half=(event['sequence']//2)%2
            team=event['team'];opp='A' if team=='H' else 'H'
            event['points']=0 if event['turnover'] else ([0,0,0,0,2,3,2,3][(event['sequence']//2)%8])
            event['offense_lineup']=g['team_rosters'][team][5*half:5*half+5]
            event['defense_lineup']=g['team_rosters'][opp][5*half:5*half+5]
        points={t:sum(e['points'] for e in g['possessions'] if e['team']==t) for t in ('H','A')}
        if points['H']==points['A']:
            g['possessions'][-1]['points']+=1
            points['A']+=1
        g['home_points'],g['away_points']=points['H'],points['A']
    return data


class EffectTests(unittest.TestCase):
    def test_ridge_matches_analytic_two_column_solution(self):
        beta,_=ridge([(0,),(0,1)],[0,100],2,1)
        self.assertAlmostEqual(beta[0],100/3,places=6)
        self.assertAlmostEqual(beta[1],100/3,places=6)

    def test_joint_player_effects_and_samples_reproducible(self):
        data=archive()
        first=fit(data,CREATED,TIP)
        self.assertEqual(first,fit(copy.deepcopy(data),CREATED,TIP))
        self.assertEqual(len(first['players']),20)
        self.assertTrue(all(p['status']=='research_effects_only' for p in first['players'].values()))
        self.assertFalse(first['independent_validation_passed'])
        self.assertEqual(first['training_possessions'],600)
        for p in first['players'].values():
            self.assertEqual(p['effect_sample_possessions'],150)
            self.assertEqual(len(p['game_ids']),3)

    def test_lineup_identity_and_provenance_fail_closed(self):
        mutations=[lambda g:g['possessions'][0]['offense_lineup'].append('p9'),
                   lambda g:g['possessions'][0]['defense_lineup'].__setitem__(0,'p0'),
                   lambda g:g.update(lineup_attribution='unknown'),
                   lambda g:g['lineup_evidence'].update(verified=False),
                   lambda g:g.update(completed_at_utc=CREATED)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                data=archive();mutate(data['games'][0])
                with self.assertRaises((KeyError,ValueError)):fit(data,CREATED,TIP)

    def test_low_exposure_and_no_off_court_comparator_are_not_zero_effects(self):
        data=archive();data['games']=data['games'][:1]
        result=fit(data,CREATED,TIP)
        self.assertTrue(all(p['offense_effect_per_100'] is None for p in result['players'].values()))
        data=archive()
        for g in data['games']:
            for e in g['possessions']:
                opp='A' if e['team']=='H' else 'H'
                e['offense_lineup']=g['team_rosters'][e['team']][:5]
                e['defense_lineup']=g['team_rosters'][opp][:5]
        self.assertTrue(all(p['defense_effect_per_100'] is None for p in fit(data,CREATED,TIP)['players'].values()))

    def test_effect_sign_convention_and_unknown_definition(self):
        self.assertEqual(player_effect_values({'effect_kind':'regularized_possession_effect_v1',
            'offense_effect_per_100':3,'defense_effect_per_100':-2,'effect_sample_possessions':150}),(3,-2,150))
        with self.assertRaises(ValueError):player_effect_values({'effect_kind':'guessed'})


class BridgeTests(unittest.TestCase):
    def test_complete_two_sided_connection_preserves_context_and_engine_pass(self):
        snapshot,context,boxes=inputs()
        original=copy.deepcopy(context)
        evidence,audit=connect(snapshot,archive(),context)
        self.assertEqual(context,original)
        self.assertEqual(audit['connected_games'],1)
        verify_seal(audit)
        for team in evidence['games']['future']['teams'].values():
            self.assertIn('non_turnover_blocks',team)
            self.assertTrue(all(p['effect_kind']=='regularized_possession_effect_v1' for p in team['players']))
            self.assertTrue(all('offense_on_off' not in p for p in team['players']))
        report=build(snapshot,evidence,boxes,simulations=100,emitted_at=CREATED)
        self.assertIsNotNone(report['games'][0]['challenger'])
        self.assertEqual(report['games'][0]['recommendation'],'PASS')
        self.assertFalse(report['production_approved'])

    def test_fit_policy_is_hashed_and_mixed_policies_rejected(self):
        snapshot,context,boxes=inputs()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No history download')):
            evidence,_=connect(snapshot,archive(),context)
            first=build(snapshot,evidence,boxes,simulations=100,emitted_at=CREATED)
        self.assertIn('player_effect_fit',first['parameters'])
        changed=copy.deepcopy(evidence)
        for team in changed['games']['future']['teams'].values():
            team['feature_derivation']['fit_parameters']['ridge_penalty']=2000
        second=build(snapshot,changed,boxes,simulations=100,emitted_at=CREATED)
        self.assertNotEqual(first['parameters_sha256'],second['parameters_sha256'])
        changed['games']['future']['teams']['H']['feature_derivation']['fit_parameters']['ridge_penalty']=3000
        with self.assertRaisesRegex(ValueError,'Mixed player-effect'):
            build(snapshot,changed,boxes,simulations=100,emitted_at=CREATED)

    def test_cli_missing_export_records_replay_and_rejects_overwrite(self):
        snapshot,context,boxes=inputs()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,value in (('snapshot',snapshot),('context',context),('boxes',boxes)):
                (root/(name+'.json')).write_text(json.dumps(value))
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/'possession_player_bridge.py'),
                     '--snapshot',str(root/'snapshot.json'),'--context',str(root/'context.json'),
                     '--boxscores',str(root/'boxes.json'),'--output-dir',str(root/'output'),'--simulations','100']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['connected_games'],0)
            sporting=json.loads((root/'output/sporting.json').read_text())
            self.assertEqual(sporting['emission_kind'],'retrospective_replay')
            verify_seal(json.loads((root/'output/source-inputs.json').read_text()))
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)

    def test_missing_opponent_and_missing_export_cover_both_sides(self):
        snapshot,context,_=inputs();context['games']['future']['teams'].pop('A')
        evidence,audit=connect(snapshot,archive(),context)
        self.assertEqual(audit['connected_games'],0)
        self.assertNotIn('A',evidence['games']['future']['teams'])
        evidence,audit=connect(snapshot,None,context)
        self.assertEqual(len(audit['games'][0]['teams']),2)
        self.assertFalse(evidence['games'])

    def test_future_export_market_input_or_wrong_snapshot(self):
        snapshot,context,_=inputs()
        context['snapshot_sha256']='bad'
        with self.assertRaises(ValueError):connect(snapshot,archive(),context)
        snapshot,context,_=inputs();data=archive();data['bookmaker_odds']=1.9
        with self.assertRaises(ValueError):connect(snapshot,data,context)
        data=archive();data['evidence']['observed_at_utc']=TIP
        evidence,audit=connect(snapshot,data,context)
        self.assertFalse(evidence['games'])
        self.assertEqual(audit['connected_games'],0)

    def test_missing_replacement_quality_is_not_inferred_from_scoring(self):
        snapshot,context,_=inputs()
        context['games']['future']['teams']['H']['players'][0].pop('replacement_quality')
        evidence,audit=connect(snapshot,archive(),context)
        self.assertEqual(audit['connected_games'],0)
        self.assertNotIn('H',evidence['games']['future']['teams'])
