import unittest
from nhl.lineup_candidate_evaluation import evaluate,metrics
class CandidateTests(unittest.TestCase):
 def test_empty_dataset_blocks_without_parameters(self):
  x=evaluate(dict(kind='nhl_lineup_labeled_dataset_v1',rows=[]),[],'2026-11-01T00:00:00Z','2026-11-03T00:00:00Z');self.assertEqual(x['status'],'blocked_insufficient_temporal_samples');self.assertIsNone(x['parameters']);self.assertIsNone(x['metrics'])
 def test_invalid_boundaries_rejected(self):
  with self.assertRaises(ValueError):evaluate(dict(kind='nhl_lineup_labeled_dataset_v1',rows=[]),[],'2026-11-03T00:00:00Z','2026-11-01T00:00:00Z')
 def test_metrics_reference(self):
  self.assertAlmostEqual(metrics([.8,.2],[1,0])['brier'],.04)
 def test_nonempty_temporal_fit_uses_disjoint_test_games(self):
  rows=[];scores=[]
  for i in range(40):
   start=('2026-11-01' if i<20 else '2026-11-03')+'T20:00:00Z'
   groups={k:dict(complete=True,per_player=[]) for k in ('new_in_projection','out_of_projection')}
   rows.append(dict(game_id=str(i),start_utc=start,feature_as_of_utc='2026-10-31T00:00:00Z',home='BOS',away='MTL',target_ml_home=i%2,features={t:dict(groups=groups) for t in ('BOS','MTL')}))
   scores.append(dict(game_id=str(i),market='ml',probabilities=dict(home=.6),prediction_as_of_utc='2026-10-31T00:00:00Z'))
  x=evaluate(dict(kind='nhl_lineup_labeled_dataset_v1',rows=rows),[dict(market_scores=scores)],'2026-11-02T00:00:00Z','2026-11-04T00:00:00Z')
  self.assertEqual(x['status'],'research_evaluated_not_approved');self.assertEqual(x['train_games'],20);self.assertEqual(x['test_game_ids'],[str(i) for i in range(20,40)]);self.assertFalse(x['production_approved'])
