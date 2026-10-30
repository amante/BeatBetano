import unittest
from nhl.pulso_prospective_compare_242 import evaluate,final_scores
class Compare242(unittest.TestCase):
 def setUp(self):
  self.a={"X":{"home":"BOS","away":"MTL","start_utc":"2026-10-30T23:00:00Z",
   "as_of":"2026-10-30T12:00:00Z","p_home":.6,"model":"baseline"}}
  self.b={"X":{**self.a["X"],"p_home":.7,"model":"shadow"}}
  self.f={"X":{"game_id":"X","home":"BOS","away":"MTL","start_utc":"2026-10-30T23:00:00Z","y":1}}
 def test_pair(self):
  result=evaluate(self.a,self.b,self.f)
  self.assertEqual(result["paired_completed"],1)
  self.assertLess(result["metrics"]["brier"]["challenger"],result["metrics"]["brier"]["baseline"])
  self.assertFalse(result["automatic_promotion"])
 def test_pending_is_not_scored(self):
  z=evaluate(self.a,self.b,{})
  self.assertIsNone(z["metrics"]);self.assertEqual(z["paired_awaiting_official_final"],["X"])
 def test_unpaired_never_scored(self):
  z=evaluate(self.a,{},self.f)
  self.assertEqual(z["paired_completed"],0);self.assertEqual(z["unpaired_baseline_only"],["X"])
 def test_identity_conflict(self):
  self.f["X"]["home"]="TOR"
  with self.assertRaises(ValueError):evaluate(self.a,self.b,self.f)
 def test_official_final(self):
  x=final_scores({"games":[{"id":13,"gameState":"OFF","startTimeUTC":"2026-10-30T23:00:00Z",
   "homeTeam":{"abbrev":"BOS","score":3},"awayTeam":{"abbrev":"MTL","score":2}}]})
  self.assertEqual(x["13"]["y"],1)
 def test_live_unscored(self):
  x=final_scores({"games":[{"id":13,"gameState":"LIVE","startTimeUTC":"2026-10-30T23:00:00Z",
   "homeTeam":{"abbrev":"BOS","score":3},"awayTeam":{"abbrev":"MTL","score":2}}]})
  self.assertEqual(x,{})
if __name__=="__main__":unittest.main()
