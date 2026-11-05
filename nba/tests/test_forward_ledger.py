import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forward_ledger import parse_schedule,seal,reconstruct,verify_observation,load_observations
from forward_capture import verify_sources,paired,capture
from forward_import import adopt
from reproducible_slate import digest
ROOT=Path(__file__).resolve().parents[2]
P=json.loads((ROOT/'reports/nba-validation-2026-11-04/prospective_protocol.json').read_text())


def scheduled(tip='2026-11-05T02:00:00Z',observed='2026-11-05T00:00:00Z',completed=False):
    return {'game_id':'g','season':2027,'home_team':'BOS','away_team':'MIL','tipoff_utc':tip,
            'observed_at_utc':observed,'source_state':'post' if completed else 'pre',
            'source_status':'STATUS_FINAL' if completed else 'STATUS_SCHEDULED','completed':completed,
            'home_points':110 if completed else None,'away_points':100 if completed else None}


def observation(created='2026-11-05T00:00:00Z',prob=.6,pred=True,final=False):
    row=scheduled(observed=created,completed=final)
    return seal({'created_at_utc':created,'protocol_sha256':digest(P),'schedule':[row],
                 'source_errors':[],'predictions':[{'game_id':'g','home_team':'BOS','away_team':'MIL',
                  'tipoff_utc':row['tipoff_utc'],'prediction_as_of_utc':created,
                  'elo_p_home':prob,'challenger_p_home':prob+.01}] if pred else []})

class ForwardLedgerTests(unittest.TestCase):
    def test_first_emission_and_one_result_per_game(self):
        a=observation();b=observation('2026-11-05T01:00:00Z',.8)
        final=observation('2026-11-05T06:00:00Z',pred=False,final=True)
        r=reconstruct([b,final,a,final],P,'2026-11-05T07:00:00Z')
        self.assertEqual(r['settled_paired_games'],1)
        self.assertEqual(r['games'][0]['first_prediction']['elo_p_home'],.6)
        self.assertIsNone(r['performance_metrics'])
        self.assertEqual(r['performance_evaluation_status'],'window_open_metrics_withheld')

    def test_missing_game_remains_in_denominator(self):
        r=reconstruct([observation('2026-11-05T06:00:00Z',pred=False,final=True)],P,'2026-11-05T07:00:00Z')
        self.assertEqual(r['scheduled_games_observed'],1)
        self.assertEqual(r['missing_pregame_games'],1)
        self.assertEqual(r['paired_games'],0)

    def test_no_backdated_posttip_prediction_or_hash_tamper(self):
        o=observation('2026-11-05T06:00:00Z')
        with self.assertRaises(ValueError):verify_observation(o)
        o=observation();o['predictions'][0]['elo_p_home']=.7
        with self.assertRaises(ValueError):verify_observation(o)

    def test_reschedule_and_conflicting_finals_not_settled(self):
        a=observation();f=observation('2026-11-05T06:00:00Z',pred=False,final=True)
        changed=copy.deepcopy(f);changed.pop('content_sha256');changed['schedule'][0]['tipoff_utc']='2026-11-05T03:00:00Z'
        r=reconstruct([a,seal(changed)],P,'2026-11-05T07:00:00Z')
        self.assertEqual(r['settled_paired_games'],0)
        self.assertIn('fixture_tipoff_utc_changed',r['games'][0]['issues'])
        changed=copy.deepcopy(f);changed.pop('content_sha256');changed['schedule'][0]['home_points']=111
        r=reconstruct([a,f,seal(changed)],P,'2026-11-05T07:00:00Z')
        self.assertEqual(r['games'][0]['status'],'final_conflict_needs_review')

    def test_live_schedule_and_source_failure_are_preserved(self):
        payload={'events':[{'id':'g','date':'2026-11-05T00:00Z','season':{'type':2,'year':2027},
            'competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'BOS'}},
                {'homeAway':'away','team':{'abbreviation':'MIL'}}],
                'status':{'type':{'state':'in','name':'STATUS_IN_PROGRESS','completed':False}}}]}]}
        rows=parse_schedule(payload,'2026-11-05T01:00:00Z')
        self.assertEqual(rows[0]['source_state'],'in')
        self.assertIsNone(rows[0]['home_points'])
        o=seal({'created_at_utc':'2026-11-05T01:00:00Z','protocol_sha256':digest(P),'schedule':rows,'predictions':[],
                'source_errors':[{'league_date':'2026-11-05','error_type':'HTTPError'}]})
        r=reconstruct([o],P,'2026-11-05T01:00:00Z')
        self.assertEqual(len(r['source_errors']),1)
        self.assertEqual(r['missing_pregame_games'],1)

    def test_scope_and_protocol_hash(self):
        o=observation();o.pop('content_sha256');o['schedule'][0]['home_team']='NY';o['predictions']=[]
        self.assertEqual(reconstruct([seal(o)],P,'2026-11-05T03:00:00Z')['scheduled_games_observed'],0)
        o=observation();p=copy.deepcopy(P);p['models']=['changed']
        with self.assertRaises(ValueError):reconstruct([o],p,'2026-11-05T03:00:00Z')
        with self.assertRaises(ValueError):parse_schedule({},'2026-11-05T03:00:00Z')

    def test_source_failure_blocks_forecasts_but_persists_eligibility(self):
        import tempfile
        import requests
        from datetime import datetime,timezone
        from unittest.mock import patch
        payload={'events':[{'id':'g','date':'2026-11-05T02:00Z','season':{'type':2,'year':2027},
          'competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'BOS'}},
            {'homeAway':'away','team':{'abbreviation':'MIL'}}],
            'status':{'type':{'state':'pre','name':'STATUS_SCHEDULED','completed':False}},
            'odds':[{'must_not_be_saved':'sentinel'}]}]}]}
        class Reply:
            def raise_for_status(self):pass
            def json(self):return payload
        class Empty(Reply):
            def json(self):return {'events':[]}
        class Client:
            def get(self,url,params,timeout):
                if params['dates']=='20261020':raise requests.HTTPError('source failed')
                return Reply() if params['dates']=='20261104' else Empty()
        class Clock:
            @staticmethod
            def now(tz):return datetime(2026,11,5,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder,patch('forward_capture.datetime',Clock):
            r=capture(P,folder,'test',session=Client())
            self.assertEqual(r['current_source_error_count'],1)
            self.assertEqual(r['scheduled_games_observed'],1)
            self.assertEqual(r['paired_games'],0)
            files=list(Path(folder).glob('observations/*.json'))
            self.assertEqual(len(files),1)
            self.assertNotIn('sentinel',files[0].read_text())

    def test_tipoff_crossed_during_calculation_is_not_emitted(self):
        from datetime import datetime,timezone
        history=[{'game_id':'old','season':2024,'tipoff_utc':'2023-12-01T00:00:00Z',
                  'home_team':'BOS','away_team':'MIL','home_points':100,'away_points':90}]
        fixture=scheduled()
        after=lambda:datetime(2026,11,5,3,tzinfo=timezone.utc)
        self.assertEqual(paired(history,[fixture],'2026-11-05T00:00:00Z',clock=after),[])

    def test_truncated_source_is_a_failure_not_an_empty_slate(self):
        with self.assertRaisesRegex(ValueError,'truncated'):
            parse_schedule({'events':[{}]*500},'2026-11-05T00:00:00Z')

    def test_archive_import_has_pretip_provenance_and_current_replay(self):
        obs=load_observations(ROOT/'reports/nba-forward')
        imported=next(o for o in obs if o['run_id']=='import-original-nov4')
        self.assertEqual(len(imported['predictions']),13)
        for p in imported['predictions']:
            self.assertLess(imported['provenance']['committed_at_utc'],p['tipoff_utc'])
        report=reconstruct(obs,P,max(o['created_at_utc'] for o in obs))
        self.assertGreaterEqual(report['paired_games'],15)
        self.assertEqual(report['missing_pregame_games'],0)
        verify_sources(P,ROOT)
        with self.assertRaisesRegex(ValueError,'committed before tipoff'):
            adopt(ROOT/'reports/nba-2026-11-04',P,'2026-11-06T00:00:00Z','blob')

if __name__=='__main__':unittest.main()
