import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from possession_challenger import candidate,audit
class Tests(unittest.TestCase):
 def test_indiana_favored_when_possessions_favor_indiana(self):
  r=candidate(.547,116.3,121.5)
  self.assertLess(r["experimental_p_home"],.547)
  self.assertLess(r["score_model_p_home"],.5)
  self.assertFalse(r["production_approved"])
 def test_non_finite_fails(self):
  with self.assertRaises(ValueError):candidate(.55,float("nan"),100)
 def test_missing_does_not_invent(self):
  self.assertIsNone(candidate(.55,None,120))
 def test_snapshot_guard(self):
  s={"content_sha256":"abc","predictions":[{"game_id":"1","home_team":"MIL","away_team":"IND","elo_p_home":.61,"challenger_p_home":.55,"hybrid_p_home":.55}]}
  p={"snapshot_sha256":"wrong","games":{}}
  with self.assertRaises(ValueError):audit(s,p)
if __name__=="__main__":unittest.main()
