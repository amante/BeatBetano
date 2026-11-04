import copy,unittest
from nhl.lineup_outcome_dataset import build
class DatasetTests(unittest.TestCase):
 def inputs(self):
  r=dict(game_id='1',home='BOS',away='MTL',start_utc='2026-11-03T00:00:00Z',frozen_at_utc='2026-11-02T18:00:00Z',complete_observed_inputs=True,teams={})
  c=dict(kind='nhl_frozen_lineup_dataset_v1',records=[r]);p=dict(kind='nhl_daily_postmortem',games=[dict(game_id='1',home='BOS',away='MTL',start_utc=r['start_utc'],state='OFF',outcomes=dict(ml_winner='home'))]);return c,p
 def test_same_game_once_earliest_complete(self):
  c,p=self.inputs();later=copy.deepcopy(c);later['records'][0]['frozen_at_utc']='2026-11-02T19:00:00Z'
  x=build([later,c],[p]);self.assertEqual(len(x['rows']),1);self.assertEqual(x['rows'][0]['feature_as_of_utc'],c['records'][0]['frozen_at_utc']);self.assertEqual(x['rows'][0]['target_ml_home'],1)
 def test_pending_and_incomplete_not_training_rows(self):
  c,p=self.inputs();self.assertEqual(build([c],[])['rows'],[]);c['records'][0]['complete_observed_inputs']=False;self.assertEqual(build([c],[p])['rows'],[])
 def test_null_outcomes_are_skipped_and_do_not_block_other_labels(self):
  c,p=self.inputs();p['games'].append(dict(game_id='2',home='TOR',away='OTT',start_utc='2026-11-03T01:00:00Z',state='OFF',outcomes=None))
  result=build([c],[p]);self.assertEqual(len(result['rows']),1);self.assertEqual(result['rows'][0]['target_ml_home'],1)
 def test_poststart_and_identity_mismatch_rejected(self):
  c,p=self.inputs();p['games'][0]['home']='CAR'
  with self.assertRaises(ValueError):build([c],[p])
  c,p=self.inputs();c['records'][0]['frozen_at_utc']=c['records'][0]['start_utc']
  with self.assertRaises(ValueError):build([c],[p])
