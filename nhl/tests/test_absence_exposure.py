import unittest
from nhl.absence_exposure import scenario
class ExposureTests(unittest.TestCase):
 def p(self,pid,minutes,goals=1):return dict(player_id=pid,name=str(pid),history=dict(skater_games=1,toi_seconds=minutes*60,skater_goals=goals,skater_assists=2,skater_shots=3,penalty_minutes=2))
 def test_minutes_conserved_and_retained_receive_balance(self):
  x=scenario(dict(status='projected_changes_observed_not_calibrated',out_of_projection=[self.p(1,20)],new_in_projection=[self.p(2,10)],projected_players=[self.p(2,10),self.p(3,20)]));self.assertEqual(x['allocated_minutes'],40);self.assertEqual(x['players'][1]['scenario_minutes'],30);self.assertEqual(x['lost_historical_contribution']['goals'],1);self.assertIsNone(x['probability_delta'])
 def test_missing_stats_remain_null(self):
  p=self.p(1,20);p['history']['skater_assists']=None
  x=scenario(dict(status='projected_changes_observed_not_calibrated',out_of_projection=[],new_in_projection=[],projected_players=[p]));self.assertIsNone(x['after']['assists']);self.assertEqual(x['delta']['goals'],0)
 def test_missing_history_blocks(self):
  x=scenario(dict(status='projected_changes_observed_not_calibrated',out_of_projection=[],new_in_projection=[],projected_players=[dict(player_id=1)]));self.assertEqual(x['status'],'blocked')
