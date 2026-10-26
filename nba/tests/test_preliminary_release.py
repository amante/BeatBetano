import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preliminary_release import publish
def sample():
 return {"command":"NBA hoy","complete_slate":True,"games_expected":1,"games":[{
 "game_id":"1","home_team":"LAL","away_team":"BOS","tipoff_utc":"2026-10-27T01:00:00Z",
 "official_baseline_p_home":.56,"challenger_baseline_p_home":.53,
 "hybrid_baseline_p_home":.53,"final_p_home":None}]}
class Test(unittest.TestCase):
 def test_screen_not_bet(self):
  x=publish(sample())["games"][0]
  self.assertTrue(x["preliminary_dual_screen"])
  self.assertFalse(x["bet_authorized"])
 def test_no_fake_final(self):
  s=sample();s["games"][0]["final_p_home"]=.7
  with self.assertRaises(ValueError):publish(s)
 def test_no_incomplete_slate(self):
  s=sample();s["complete_slate"]=False
  with self.assertRaises(ValueError):publish(s)
if __name__=="__main__":unittest.main()
