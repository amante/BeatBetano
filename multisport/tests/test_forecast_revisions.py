import copy
import tempfile
import unittest
from pathlib import Path
from multisport.contract import SPORTS, validate_report
from multisport.sport_adapters import adapt
from multisport.forecast_revisions import snapshot, save_snapshot, verify_snapshot


def source(sport, p=.55, stamp='2026-11-06T10:00:00Z'):
    event={'event_id':'1','game_id':'1','start_utc':'2026-11-07T20:00:00Z',
           'home':'A','away':'B','model_version':'test-model',
           'forecast_probabilities':{'home':p,'away':1-p},
           'assumptions':['Expected rotation, not confirmed starters'],
           'unresolved_inputs':['Starting lineup','Player availability']}
    if sport=='soccer':event['forecast_probabilities']={'home':.5,'draw':.3,'away':.2}
    key='predictions' if sport=='nba' else 'games' if sport=='nhl' else 'events'
    return {'as_of_utc':stamp,'odds_used':False,key:[event]}


class RevisionTests(unittest.TestCase):
    def test_all_sports_publish_without_confirmed_players(self):
        for sport in SPORTS:
            for stage in ('initial','update','final_pregame'):
                r=adapt(sport,source(sport),stage=stage)
                event=r['events'][0]
                self.assertIsNotNone(event['forecast'])
                self.assertIsNone(event['final_probability'])
                self.assertEqual(event['forecast']['stage'],stage)
                self.assertEqual(event['forecast']['selection_status'],'PASS')
                self.assertEqual(validate_report(r)['published_forecasts'],1)
                self.assertEqual(validate_report(r)['verified_probabilities'],0)

    def test_revisions_preserve_initial_probability_and_explain_changes(self):
        first=snapshot(adapt('nba',source('nba')))
        original=copy.deepcopy(first)
        second=snapshot(adapt('nba',source('nba',.6,'2026-11-06T11:00:00Z'),stage='update'),first)
        self.assertEqual(first,original)
        self.assertEqual(second['revision'],2)
        self.assertEqual(second['parent_snapshot_sha256'],first['content_sha256'])
        self.assertEqual(second['changes'][0]['before']['probabilities']['home'],.55)
        self.assertEqual(second['changes'][0]['after']['probabilities']['home'],.6)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'initial.json'
            save_snapshot(p,first)
            with self.assertRaises(FileExistsError):save_snapshot(p,second)

    def test_tampering_or_changing_identity_cannot_rewrite_history(self):
        first=snapshot(adapt('nba',source('nba')))
        first['events'][0]['forecast']['probabilities']['home']=.7
        with self.assertRaisesRegex(ValueError,'digest'):verify_snapshot(first)
        first=snapshot(adapt('nba',source('nba')))
        next_report=adapt('nba',source('nba',.6,'2026-11-06T11:00:00Z'),stage='update')
        next_report['events'][0]['participants']=['C','B']
        with self.assertRaisesRegex(ValueError,'identity'):snapshot(next_report,first)

    def test_missing_baseline_is_not_fabricated_and_prices_rejected(self):
        s=source('nba');s['predictions'][0].pop('forecast_probabilities')
        self.assertIsNone(adapt('nba',s)['events'][0]['forecast'])
        s=source('nba');s['odds_used']=True
        with self.assertRaisesRegex(ValueError,'Market'):adapt('nba',s)
        for bad in (float('nan'),True,-.1):
            s=source('nba',p=bad)
            with self.assertRaises(ValueError):adapt('nba',s)

    def test_real_legacy_nba_fields_are_published_as_baseline_not_certified(self):
        s=source('nba');event=s['predictions'][0]
        event.pop('forecast_probabilities');event['elo_p_home']=.58
        out=adapt('nba',s)['events'][0]
        self.assertEqual(out['forecast']['probabilities']['home'],.58)
        self.assertTrue(out['source_candidate_available'])
        self.assertIsNone(out['final_probability'])

    def test_future_sources_and_backwards_revisions_rejected(self):
        first=snapshot(adapt('nba',source('nba'),stage='final_pregame'))
        with self.assertRaisesRegex(ValueError,'backwards'):
            snapshot(adapt('nba',source('nba',.6,'2026-11-06T11:00:00Z'),stage='update'),first)
        with self.assertRaises(ValueError):snapshot(adapt('nba',source('nba')),first)
        with self.assertRaises(ValueError):adapt('nba',source('nba',stamp='2026-11-08T00:00:00Z'))
        s=source('nba');s['predictions'][0]['observed_at_utc']='2026-11-06T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'cutoff'):adapt('nba',s)
        s=source('nba');s['predictions'][0]['observed_at_utc']='2026-11-06T10:00:00.001Z'
        with self.assertRaisesRegex(ValueError,'cutoff'):adapt('nba',s)

    def test_soccer_vector_not_replaced_with_binary_complement(self):
        s=source('soccer');s['events'][0]['forecast_probabilities']['away']=.3
        with self.assertRaisesRegex(ValueError,'sum to one'):adapt('soccer',s)
