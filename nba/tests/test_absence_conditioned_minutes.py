import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from absence_conditioned_minutes import conditioned_weights
T="2026-10-29T01:00:00Z"
def hist(i,out,minute,verified=True):
 return {"game_id":str(i),"team":"OKC","tipoff_utc":f"2026-10-{i+10:02d}T01:00:00Z",
  "availability_verified":verified,"confirmed_out_player_ids":["star"] if out else [],
  "player_minutes":{"bench":minute}}
class Tests(unittest.TestCase):
 def test_verified_absence_increases_expected_weight(self):
  games=[hist(i,False,14) for i in range(3)]+[hist(i+3,True,28) for i in range(3)]
  x=conditioned_weights(T,"OKC",["bench"],["star"],games)["weights"]["bench"]
  self.assertEqual(x["status"],"conditional_shrunk")
  self.assertGreater(x["weight"],21)
  self.assertLess(x["weight"],28)
 def test_unverified_games_excluded(self):
  games=[hist(i,False,14) for i in range(3)]+[hist(i+3,True,40,False) for i in range(3)]
  x=conditioned_weights(T,"OKC",["bench"],["star"],games)["weights"]["bench"]
  self.assertEqual(x["weight"],14)
  self.assertEqual(x["observed_conditional_games"],0)
 def test_future_leakage_excluded(self):
  games=[hist(i,False,14) for i in range(3)]
  games.append(dict(hist(8,True,45),tipoff_utc="2026-11-01T01:00:00Z"))
  x=conditioned_weights(T,"OKC",["bench"],["star"],games)["weights"]["bench"]
  self.assertEqual(x["weight"],14)
 def test_missing_baseline_does_not_make_up_weight(self):
  x=conditioned_weights(T,"OKC",["bench"],["star"],[])["weights"]["bench"]
  self.assertIsNone(x["weight"])
 def test_absent_cannot_be_eligible(self):
  with self.assertRaises(ValueError):conditioned_weights(T,"OKC",["star"],["star"],[])
if __name__=="__main__":unittest.main()
