import unittest
from nhl.pulso_sporting_benchmark_239 import evaluate,outcome_baseline,score,reliability
class Benchmark239(unittest.TestCase):
 def labels(self):
  return [{"game_id":str(i),"date":f"2026-03-{i+1:02d}","home":"BOS","away":"MTL",
           "ml_winner":"home" if i%2 else "away"} for i in range(4)]
 def challenger(self):
  return {"status":"research_only_challenger_fitted","promoted":False,
    "holdout_start":"2026-03-02","holdout_games":2,
    "holdout_predictions":[{"game_id":"1","date":"2026-03-02","p_home_ml":.6,"actual_home_ml":1},
                           {"game_id":"3","date":"2026-03-04","p_home_ml":.7,"actual_home_ml":1}]}
 def test_paired(self):
  x=evaluate(self.challenger(),self.labels())
  self.assertEqual(x["paired_games"],2)
  self.assertEqual(x["overall"]["challenger"]["n"],2)
  self.assertFalse(x["model_promoted"])
 def test_no_missing_games(self):
  with self.assertRaises(ValueError):evaluate(self.challenger(),self.labels()[:2])
 def test_wrong_label(self):
  c=self.challenger();c["holdout_predictions"][0]["actual_home_ml"]=0
  with self.assertRaises(ValueError):evaluate(c,self.labels())
 def test_duplicate_holdout(self):
  c=self.challenger();c["holdout_predictions"][1]["game_id"]="1"
  with self.assertRaises(ValueError):evaluate(c,self.labels())
 def test_invalid_probability(self):
  with self.assertRaises(ValueError):score([(1.1,1)])
 def test_brier(self):
  self.assertAlmostEqual(score([(.8,1),(.2,0)])["brier"],.04)
 def test_no_same_day_leakage(self):
  labels=[{"game_id":str(i),"date":"2026-03-01","home":"BOS","away":"MTL","ml_winner":"home"} for i in range(5)]
  out=outcome_baseline(labels,set(str(i) for i in range(5)))
  self.assertEqual(len({out[str(i)]["p_home_ml"] for i in range(5)}),1)
 def test_reliability(self):
  self.assertEqual(sum(x["n"] for x in reliability([(.1,0),(.9,1)])),2)
if __name__=="__main__":unittest.main()
