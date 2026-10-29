import unittest
from nhl.pulso_player_v1 import validate,forecast,replay
def row(i,day,sog=3,home=True,opponent="ANA"):
 return {"game_id":str(i),"date":day,"player_id":"97","team":"EDM",
 "opponent":opponent,"home":home,"rest_days":1,
 "toi_minutes":21.0,"shots_on_goal":sog,"goals":0}
class PulsoPlayerTests(unittest.TestCase):
 def test_no_target_day_leakage(self):
  rows=validate([row(1,"2026-10-01",2),row(2,"2026-10-02",9),row(3,"2026-10-03",4)])
  target={"player_id":"97","team":"EDM","opponent":"LAK","home":False,"rest_days":0}
  p=forecast(rows,target,"2026-10-03",minimum=2)
  self.assertAlmostEqual(p["unconditional_average"]["shots_on_goal"],5.5)
  self.assertNotEqual(p["unconditional_average"]["shots_on_goal"],5.0)
 def test_missing_history_not_invented(self):
  p=forecast([],{"player_id":"97","team":"EDM","opponent":"ANA","home":False,"rest_days":0},"2026-10-12")
  self.assertIsNone(p["projection"])
 def test_replay_compares_both_on_same_rows(self):
  rows=validate([row(i,f"2026-10-{i:02d}",i%5+1) for i in range(1,8)])
  r=replay(rows,"2026-10-04")
  self.assertEqual(r["observations"],4)
  self.assertEqual(r["scores"]["shots_on_goal"]["n"],4)
 def test_duplicate_game_player_rejected(self):
  with self.assertRaises(ValueError):validate([row(1,"2026-10-01"),row(1,"2026-10-01")])
if __name__=="__main__":unittest.main()
