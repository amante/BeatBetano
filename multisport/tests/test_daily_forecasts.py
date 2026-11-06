import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from multisport.daily_forecasts import publish,latest,_directory
from multisport.daily_pipeline import run, soccer_source
from multisport.tests.test_forecast_revisions import source


class DailyTests(unittest.TestCase):
    def test_all_sport_real_output_shapes_and_revision_cohort_changes(self):
        with tempfile.TemporaryDirectory() as d:
            for sport in ('nba','nfl','nhl','soccer','tennis'):
                s=source(sport)
                # Real NHL CLI emits events, not games; NFL publishes this exact field.
                if sport=='nhl':s['events']=s.pop('games')
                if sport=='nfl':
                    s['events'][0].pop('forecast_probabilities');s['events'][0]['historical_elo_candidate']=.55
                first=publish(sport,s,d)
                self.assertEqual(first['events'][0]['stage'],'initial')
                self.assertEqual(publish(sport,s,d)['events'][0]['status'],'reused')
                s['as_of_utc']='2026-11-06T11:00:00Z'
                key='predictions' if sport=='nba' else 'events'
                s[key].append(dict(s[key][0],event_id='2',game_id='2'))
                revised=publish(sport,s,d)
                self.assertEqual([e['stage'] for e in revised['events']],['update','initial'])
                self.assertEqual(latest(_directory(d,sport,'1'))['revision'],2)
                # A fixture leaving the slate does not break remaining event chains.
                s['as_of_utc']='2026-11-06T12:00:00Z';s[key]=s[key][1:]
                self.assertEqual(publish(sport,s,d)['events'][0]['revision'],2)

    def test_missing_source_retains_archive_and_final_is_not_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            s=source('nba',stamp='2026-11-06T10:00:00Z')
            s['predictions'][0]['start_utc']='2026-11-06T10:15:00Z'
            first=publish('nba',s,d)
            self.assertEqual(first['events'][0]['stage'],'final_pregame')
            s['as_of_utc']='2026-11-06T10:05:00Z';s['predictions'][0].pop('forecast_probabilities')
            result=publish('nba',s,d)
            self.assertEqual(result['events'][0]['status'],'no_source_probability')
            old=latest(_directory(d,'nba','1'))
            self.assertEqual(old['revision'],1)
            self.assertEqual(result['events'][0]['latest_snapshot_sha256'],old['content_sha256'])

    def test_failure_isolated_and_no_tennis_probability_invented(self):
        now=datetime.now(timezone.utc);start=(now+timedelta(days=1)).isoformat()
        feed={'games':[{'id':sport,'sport':sport,'start_utc':start,'status':'STATUS_SCHEDULED',
                        'home':'A','away':'B','completed':False} for sport in ('nba','nfl','nhl','soccer','tennis')]}
        def provider(sport,games,asof,*args):
            if sport=='nhl':raise ValueError('standings unavailable')
            s=source(sport,stamp=asof)
            key='predictions' if sport=='nba' else 'games' if sport=='nhl' else 'events'
            e=s[key][0];e.update(start_utc=start,event_id=sport,game_id=sport)
            if sport=='tennis':e.pop('forecast_probabilities')
            return s
        with tempfile.TemporaryDirectory() as d:
            result=run(feed,d,d,provider)
            self.assertEqual(result['sports']['nba']['fixtures_with_forecast'],1)
            self.assertEqual(result['sports']['nhl']['status'],'source_error')
            self.assertEqual(result['sports']['tennis']['missing_baseline_fixture_ids'],['tennis'])
            self.assertEqual(result['status'],'partial_source_failure')

    def test_empty_day_still_produces_persistable_archive_directory(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'archive'
            result=run({'games':[]},archive,d,lambda *args: self.fail('No source request needed'))
            self.assertTrue(archive.is_dir())
            self.assertTrue(all(s['status']=='no_pending_fixtures' for s in result['sports'].values()))
            self.assertEqual(result['status'],'completed')

    def test_conflicting_same_cutoff_and_broken_chain_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s=source('nba');publish('nba',s,d)
            s['predictions'][0]['forecast_probabilities']={'home':.7,'away':.3}
            with self.assertRaisesRegex(ValueError,'identical'):publish('nba',s,d)
            p=_directory(d,'nba','1')/'000001.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'digest'):publish('nba',s,d)


class SoccerDailyTests(unittest.TestCase):
    def test_existing_model_only_maps_supported_league_and_team_identities(self):
        from unittest.mock import patch
        rows=[{'date':'2026-01-01','home':'Arsenal FC','away':'Chelsea FC','hg':2,'ag':1},
              {'date':'2026-01-02','home':'Chelsea FC','away':'Arsenal FC','hg':1,'ag':1}]
        games=[{'id':'1','home':'Arsenal','away':'Chelsea','league':'Premier League','start_utc':'2026-11-07T15:00:00Z'},
               {'id':'2','home':'Arsenal','away':'Chelsea','league':'La Liga','start_utc':'2026-11-07T15:00:00Z'},
               {'id':'3','home':'Arsenal','away':'Unknown','league':'Premier League','start_utc':'2026-11-07T15:00:00Z'}]
        with tempfile.TemporaryDirectory() as d, patch('soccer.data.load_history',return_value=(rows,[])):
            result=soccer_source(games,'2026-11-06T10:00:00Z',d)
            self.assertAlmostEqual(sum(result['events'][0]['probabilities']),1)
            self.assertNotIn('probabilities',result['events'][1])
            self.assertNotIn('probabilities',result['events'][2])
            # An unchanged source/model policy reuses its fitted model.
            with patch('soccer.poisson.fit',side_effect=AssertionError('Do not refit unchanged model')):
                self.assertEqual(result,soccer_source(games,'2026-11-06T10:00:00Z',d))
