from datetime import datetime
import copy
import tempfile
from pathlib import Path
import unittest
from nhl.tests.test_player_evidence import inputs
from nhl.tests.test_goalie_prospective_evaluation import fixture
from nhl.tests.test_goalie_ml_inference import fitted_artifact,slate,AT
from nhl.pulso_goalie_scenarios_258 import build,editorial_candidates
from nhl.pulso_goalie_candidates_260 import collect
from nhl.goalie_ml_inference import infer_pairings


def data():
    report,rosters,_,_,article=inputs()
    for i,team in enumerate(('BOS','VGK')):
        name=team+' Reserve'
        rosters[i]['players'].append(dict(player_id=3000+i,full_name=name,position_group='goalie'))
        article=article.replace(('<p>'+team+' Goalie</p>').encode(),('<p>'+team+' Goalie</p><p>'+name+'</p>').encode())
    projected,issues=editorial_candidates(report,rosters,article)
    ident=dict(kind='nhl_fixture_identity_gate_248',as_of_utc=report['generated_at_utc'],games=[dict(game_id='2026020232',home='BOS',away='VGK',teams={t:dict(source_goalie_player_id=2000+i,source_goalie_name=t+' Goalie') for i,t in enumerate(('BOS','VGK'))})])
    external=dict(kind='nhl_external_goalie_observations_257',as_of_utc=report['generated_at_utc'],observations=[])
    scenarios=build(report,ident,external,editorial_observations=projected,editorial_issues=issues)
    def fetch(pid,season):
        saves=18 if pid<3000 else 19
        return {'gameLog':[dict(gameDate='2026-11-01',gameId=1,shotsAgainst=20,saves=saves,goalsAgainst=20-saves)]},dict(url='https://api-web.nhle.com/v1/player/'+str(pid)+'/game-log/'+season+'/2',sha256='a'*64,retrieved_at='2026-11-02T19:30:00Z')
    history=collect(scenarios,report,fetch)
    return report,rosters,article,scenarios,history


class AllGoaliePairings(unittest.TestCase):
    def test_second_goalie_is_included_without_guessing_starter(self):
        _,_,_,scenarios,history=data()
        g=scenarios['games'][0]
        self.assertEqual(g['scenario_count'],4)
        self.assertEqual({(p['home_goalie']['player_id'],p['away_goalie']['player_id']) for p in g['scenarios']},{(2000,2001),(2000,3001),(3000,2001),(3000,3001)})
        self.assertEqual(history['distinct_candidate_ids'],4)

    def test_all_pairs_have_separate_predictions_when_model_is_available(self):
        _,_,_,scenarios,history=data()
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp));r=infer_pairings(temp,'123',slate()['games'][0],scenarios,history,fitted_artifact(),AT)
            self.assertEqual(len(r['pairings']),4)
            probs=[p['candidate_p_home'] for p in r['pairings']]
            self.assertGreater(max(probs),min(probs))
            self.assertTrue(all(p['status']=='experimental_goalie_ml_executed' for p in r['pairings']))
            self.assertTrue(all(abs(p['candidate_p_home']+p['candidate_p_away']-1)<1e-9 for p in r['pairings']))

    def test_missing_model_keeps_all_four_pairs_with_nulls(self):
        _,_,_,scenarios,history=data()
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp));r=infer_pairings(temp,'123',slate()['games'][0],scenarios,history,None,AT)
            self.assertEqual(len(r['pairings']),4)
            self.assertTrue(all(p['candidate_p_home'] is None and p['delta_vs_baseline_pp'] is None for p in r['pairings']))

    def test_missing_one_history_blocks_only_its_two_pairs(self):
        _,_,_,scenarios,history=data();history['games'][0]['teams']['BOS'][1]['status']='no_prior_games'
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp));r=infer_pairings(temp,'123',slate()['games'][0],scenarios,history,fitted_artifact(),AT)
            self.assertEqual(sum(p['status']=='experimental_goalie_ml_executed' for p in r['pairings']),2)

    def test_old_article_does_not_reuse_candidate_names(self):
        report,rosters,article,_,_=data()
        projected,_=editorial_candidates(report,rosters,article.replace(b'2026-11-02T18:30',b'2026-11-01T18:30'))
        self.assertEqual(projected,{})

    def test_incomplete_cartesian_product_is_rejected(self):
        _,_,_,scenarios,history=data();scenarios['games'][0]['scenarios'].pop()
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp))
            with self.assertRaises(ValueError):infer_pairings(temp,'123',slate()['games'][0],scenarios,history,None,AT)
