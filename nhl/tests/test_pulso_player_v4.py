import math,unittest
from nhl.pulso_player_v4 import poisson_probs,bin_probability,binary_scores,replay,summarize,bootstrap_interval
from nhl.pulso_player_v1 import validate

class V4Tests(unittest.TestCase):
 def test_poisson_distribution(self):
  probs=poisson_probs(2.4)
  self.assertAlmostEqual(sum(probs),1.,places=9)
  self.assertAlmostEqual(probs[0],math.exp(-2.4))
  self.assertAlmostEqual(bin_probability(2.4),1-probs[0])
 def test_zero_rate_and_invalid_rate(self):
  self.assertEqual(bin_probability(0),0)
  self.assertEqual(poisson_probs(0)[0],1)
  with self.assertRaises(ValueError):poisson_probs(-1)
 def test_binary_metrics(self):
  metrics=binary_scores([.1,.9],[0,1])
  self.assertAlmostEqual(metrics["brier"],.01)
  self.assertEqual(metrics["n"],2)
 def test_chronological_roll_10(self):
  rows=[]
  for i in range(12):
   rows.append({"game_id":str(i),"date":"2026-01-%02d"%(i+1),"player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":10+i,"shots_on_goal":i%4,"goals":0})
  rows=validate(rows)
  predictions=replay(rows,{"97":"C"},start="2026-01-01")
  self.assertEqual(len(predictions),2)
  self.assertAlmostEqual(predictions[0]["predictions"]["recent10"]["toi_minutes"],14.5)
  self.assertEqual(predictions[0]["date"],"2026-01-11")
  self.assertIsNone(bootstrap_interval(predictions))
  self.assertEqual(summarize(predictions)["all"]["toi_minutes"]["n"],2)
 def test_same_day_never_enters_history(self):
  rows=[]
  for i in range(10):
   rows.append({"game_id":str(i),"date":"2026-01-%02d"%(i+1),"player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":10,"shots_on_goal":0,"goals":0})
  rows.append({"game_id":"10","date":"2026-01-11","player_id":"97","team":"EDM","opponent":"LAK","home":True,"rest_days":1,"toi_minutes":60,"shots_on_goal":10,"goals":5})
  predictions=replay(validate(rows),{"97":"C"},start="2026-01-11")
  self.assertEqual(predictions[0]["predictions"]["recent10"]["toi_minutes"],10)
  self.assertEqual(predictions[0]["predictions"]["recent10"]["goals"],0)
if __name__=="__main__":unittest.main()
