import hashlib,json,unittest
from nba.pulso_publication import build
class PublicationTests(unittest.TestCase):
 def snapshot(self):
  x=dict(created_at_utc='2026-11-03T15:00:00Z',predictions=[dict(game_id='1',tipoff_utc='2026-11-04T00:00:00Z',home_team='BOS',away_team='NYK',elo_p_home=.6,challenger_p_home=.55,hybrid_p_home=.6)],calibrated=False)
  return self.sign(x)
 def sign(self,x):
  x.pop('content_sha256',None);x['content_sha256']=hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();return x
 def test_preserves_probabilities_and_limits(self):
  s=self.snapshot();x=build(s,'123');self.assertEqual(x['predictions'],s['predictions']);self.assertFalse(x['calibrated']);self.assertFalse(x['availability_and_lineups_included'])
 def test_modified_snapshot_rejected(self):
  x=self.snapshot();x['predictions'][0]['elo_p_home']=.7
  with self.assertRaises(ValueError):build(x,'123')
 def test_poststart_and_bad_probability_rejected(self):
  for key,value in [('tipoff_utc','2026-11-03T14:00:00Z'),('hybrid_p_home',1.2)]:
   x=self.snapshot();x['predictions'][0][key]=value
   with self.assertRaises(ValueError):build(self.sign(x),'123')
