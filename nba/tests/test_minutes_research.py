import copy
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from minutes_research import episodes,features,fit,predict,solve,evaluate
from minutes_prospective import forecast
from reproducible_slate import digest
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'reports/nba-minutes-research-2026-11-05'
P=json.loads((FOLDER/'protocol.json').read_text())


def game(i,minutes,dnp=False):
    return {'game':{'game_id':str(i),'home_team':'A','away_team':'B','tipoff_utc':f'2026-10-{20+i:02d}T00:00:00Z'},
            'observed_at_utc':'2026-11-04T21:00:00Z',
            'players':[{'game_id':str(i),'team':t,'player_id':t+'1','player':t+' Player','minutes_played':minutes,'did_not_play':dnp} for t in ('A','B')]}

class MinutesResearchTests(unittest.TestCase):
    def test_current_game_target_never_enters_own_features(self):
        archive={'games':[game(0,10),game(1,20),game(2,30),game(3,40)]}
        rows,_=episodes(archive,P)
        self.assertEqual(rows[0]['baseline'],20)
        self.assertEqual(rows[0]['prior_game_ids'],['0','1','2'])
        changed=copy.deepcopy(archive);changed['games'][-1]['players'][0]['minutes_played']=1
        second,_=episodes(changed,P)
        self.assertEqual(rows[0]['x'],second[0]['x'])
        self.assertNotEqual(rows[0]['y'],second[0]['y'])

    def test_dnp_missing_targets_and_unseen_players_are_not_zero_labels(self):
        archive={'games':[game(0,10),game(1,20),game(2,30),game(3,None,True),game(4,40)]}
        rows,coverage=episodes(archive,P)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['baseline'],20)
        self.assertEqual(coverage[3]['explicit_dnp_rows'],2)
        self.assertEqual(coverage[3]['scored_appearances'],0)
        archive['games'][4]['players'].pop()
        rows,coverage=episodes(archive,P)
        self.assertEqual(len(rows),1)
        self.assertEqual(coverage[-1]['prior_players_missing_target_row'],1)

    def test_same_tipoff_and_recent_unfinished_history_cannot_enter_features(self):
        tip=datetime(2026,11,1,tzinfo=timezone.utc)
        prior=[{'tip':tip,'game_id':str(i),'minutes':20} for i in range(3)]
        self.assertIsNone(features(prior,tip,P))

    def test_duplicate_invalid_minute_and_cross_team_id_rejected(self):
        g=game(0,10)
        with self.assertRaises(ValueError):episodes({'games':[g,g]},P)
        for m in (float('nan'),True,-1,66):
            with self.assertRaises(ValueError):episodes({'games':[game(0,m)]},P)
        g=game(0,10);g['players'][1]['player_id']='A1'
        with self.assertRaises(ValueError):episodes({'games':[g]},P)

    def test_ridge_constant_target_and_solver(self):
        model=fit([{'x':[1,1,1,3,1],'y':12,'tipoff_utc':'2026-10-25T00:00:00Z'} for _ in range(10)],10)
        self.assertAlmostEqual(predict(model,[1,1,1,3,1]),12)
        self.assertEqual(solve([[2,0],[0,2]],[2,4]),[1,2])
        with self.assertRaises(ValueError):predict(model,[1])

    def test_live_projection_keeps_expected_minutes_and_full_allocation_null(self):
        a={'games':[game(0,10),game(1,20),game(2,30)]}
        model=fit([{'x':[1,1,1,3,1],'y':12,'tipoff_utc':'2026-10-25T00:00:00Z'} for _ in range(10)],10)
        source={'ref':'one','availability':{'games':{'future':{'teams':{'A':{
            'observed_at_utc':'2026-11-05T00:00:00Z','roster_complete':True,
            'players':[{'player_id':'A1','player':'Player','status':'unknown'}, {'player_id':'new','player':'New','status':'out'}]}}}}},'lineups':{'games':{}}}
        fixture={'game_id':'future','home_team':'A','away_team':'B','tipoff_utc':'2026-11-06T00:00:00Z'}
        r=forecast(a,model,P,[fixture],[source],'2026-11-05T01:00:00Z')
        players=r['games'][0]['teams']['A']['players']
        self.assertIsNotNone(players[0]['conditional_candidate_minutes'])
        self.assertIsNone(players[0]['expected_game_minutes'])
        self.assertIsNone(players[0]['participation_probability'])
        self.assertIsNone(players[1]['conditional_candidate_minutes'])
        self.assertIsNone(r['games'][0]['teams']['A']['regulation_allocations'])
        a['games'][0]['observed_at_utc']='2026-11-06T00:00:00Z'
        r=forecast(a,model,P,[fixture],[source],'2026-11-05T01:00:00Z')
        self.assertIsNone(r['games'][0]['teams']['A']['players'][0]['conditional_candidate_minutes'])

    def test_research_archive_integrity_and_future_semantics(self):
        import hashlib
        manifest=json.loads((FOLDER/'manifest.json').read_text())
        for name,sha in manifest['files'].items():
            self.assertEqual(hashlib.sha256((FOLDER/name).read_bytes()).hexdigest(),sha)
        for name,sha in manifest['model_source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha)
        future=json.loads((FOLDER/'prospective.json').read_text())
        self.assertEqual(digest({k:v for k,v in future.items() if k!='content_sha256'}),future['content_sha256'])
        self.assertEqual(len(future['games']),2)
        for g in future['games']:
            self.assertLess(future['created_at_utc'],g['tipoff_utc'])
            for team in g['teams'].values():
                self.assertIsNone(team['regulation_allocations'])
                for player in team['players']:
                    self.assertIsNone(player['expected_game_minutes'])
                    self.assertIsNone(player['participation_probability'])
        self.assertFalse(future['ml_modified'])

    def test_real_archive_replay_and_holdout_targets_cannot_fit_coefficients(self):
        archive=json.loads((ROOT/'reports/nba-2026-11-04/boxscores.json').read_text())
        expected=json.loads((FOLDER/'evaluation.json').read_text());actual=evaluate(archive,P)
        self.assertEqual(actual['split_rows'],{'train':273,'validation':280,'test':612})
        for name,m in expected['test_metrics'].items():
            for metric in ('mae','rmse','bias'):
                self.assertAlmostEqual(actual['test_metrics'][name][metric],m[metric],delta=1e-10)
        changed=copy.deepcopy(archive)
        for item in changed['games']:
            if item['game']['tipoff_utc']>='2026-10-31T00:00:00Z':
                for p in item['players']:
                    if p['minutes_played'] is not None:p['minutes_played']=1
        altered=evaluate(changed,P)
        self.assertEqual(altered['model_sha256'],actual['model_sha256'])
        self.assertEqual(altered['validation_selection'],actual['validation_selection'])
        self.assertFalse(actual['production_approved'])

if __name__=='__main__':unittest.main()
