import math,unittest
from nhl.joint_goal_model import FEATURES,predict,fit
class JointTests(unittest.TestCase):
 def model(self):return dict(kind='nhl_joint_goal_model_v1',features=list(FEATURES),means=[0]*10,scales=[1]*10,weights=[.01]*10,bias=math.log(2))
 def side(self):return {k:.5 for k in FEATURES}
 def test_every_feature_is_connected_in_test_parameterization(self):
  # Synthetic parameters only: connectivity is not evidence of predictive value.
  m=self.model();side=self.side();base=predict(side,side,m)
  for key in FEATURES:
   changed=dict(side);changed[key]+=.1;x=predict(changed,side,m);self.assertNotEqual(x['ml']['home'],base['ml']['home'])
 def test_markets_share_one_goal_process(self):
  x=predict(self.side(),self.side(),self.model());self.assertAlmostEqual(sum(x['ml'].values()),1);self.assertAlmostEqual(sum(x['rt'].values()),1);self.assertAlmostEqual(x['ml']['home'],.5)
 def test_missing_and_unidentifiable_block(self):
  with self.assertRaises(ValueError):predict({},self.side(),self.model())
  with self.assertRaises(ValueError):fit([])
  with self.assertRaises(ValueError):fit([dict(features=self.side(),regulation_goals=2)]*20)
