import unittest
from nhl.lineup_features import aggregate,build
class FeaturesTests(unittest.TestCase):
 def player(self,pid=1):return dict(player_id=pid,history=dict(skater_games=2,skater_goals=1,skater_shots=6,toi_games=2,toi_seconds=2400))
 def test_rates_are_observed_and_unweighted(self):
  x=aggregate([self.player()]);self.assertEqual(x['mean_historical_toi_minutes'],20);self.assertEqual(x['per_player'][0]['shots_per_game'],3)
 def test_missing_never_becomes_zero(self):
  x=aggregate([self.player(),dict(player_id=2,history=None)]);self.assertFalse(x['complete']);self.assertIsNone(x['mean_historical_toi_minutes']);self.assertEqual(x['observed_players'],1)
 def test_empty_group_is_not_zero_minutes(self):
  self.assertIsNone(aggregate([])['mean_historical_toi_minutes'])
 def test_invalid_counts_rejected(self):
  p=self.player();p['history']['toi_seconds']=-1
  with self.assertRaises(ValueError):aggregate([p])
 def test_blocked_projection_remains_blocked(self):
  x=build(dict(kind='nhl_projected_lineup_changes_v1',games=[dict(game_id='1',teams=dict(BOS=dict(status='blocked',reason='missing_projection')))]));self.assertEqual(x['games'][0]['teams']['BOS']['status'],'blocked');self.assertFalse(x['probabilities_modified'])
