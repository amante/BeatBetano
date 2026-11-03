import unittest
from nhl.prior_lineup_reference import participants
class ReferenceTests(unittest.TestCase):
 def sample(self):return dict(id=1,gameState='OFF',homeTeam=dict(abbrev='BOS'),awayTeam=dict(abbrev='MTL'),playerByGameStats=dict(homeTeam=dict(forwards=[dict(playerId=123,toi='18:32',name=dict(default='Player'))],defense=[],goalies=[dict(playerId=456,toi='00:00')])) )
 def test_only_actual_participants(self):
  x=participants(self.sample(),'BOS','1');self.assertEqual(len(x['players']),1);self.assertEqual(x['players'][0]['observed_toi_seconds'],1112);self.assertFalse(x['expected_lineup'])
 def test_wrong_identity_or_unfinished(self):
  for team,gid in [('CAR','1'),('BOS','2')]:
   with self.assertRaises(ValueError):participants(self.sample(),team,gid)
  x=self.sample();x['gameState']='LIVE'
  with self.assertRaises(ValueError):participants(x,'BOS','1')
 def test_missing_toi_and_duplicates_rejected(self):
  x=self.sample();x['playerByGameStats']['homeTeam']['forwards'][0]['toi']=''
  with self.assertRaises(ValueError):participants(x,'BOS','1')
  x=self.sample();x['playerByGameStats']['homeTeam']['forwards']*=2
  with self.assertRaises(ValueError):participants(x,'BOS','1')
