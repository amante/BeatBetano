import unittest
from nhl.minute_adjusted_ml import adjust,win_probability,build
class MinuteTests(unittest.TestCase):
 def side(self,before=3,after=3):return dict(status='conditional_replacement_scenario',before=dict(goals=before),after=dict(goals=after))
 def test_unchanged_usage_preserves_baseline(self):
  for p in (.2,.5,.8):self.assertAlmostEqual(adjust(dict(ml=dict(home=p)),self.side(),self.side())['scenario_ml_home'],p,places=10)
 def test_direction_and_complement(self):
  x=adjust(dict(ml=dict(home=.6)),self.side(3,3.2),self.side());self.assertGreater(x['scenario_ml_home'],.6);self.assertAlmostEqual(x['scenario_ml_home']+x['scenario_ml_away'],1)
 def test_missing_rejected(self):
  with self.assertRaises(ValueError):adjust(dict(ml=dict(home=.5)),self.side(3,None),self.side())
 def test_started_fixture_not_reissued(self):
  x=build(dict(games=[dict(game_id='1',home='BOS',away='MTL',start_utc='2026-11-03T00:00:00Z')]),dict(games=[]),'2026-11-03T00:00:00Z');self.assertEqual(x['games'],[])
