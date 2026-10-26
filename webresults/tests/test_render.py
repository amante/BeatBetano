import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from webresults.render import build
class Tests(unittest.TestCase):
 def test_nhl_table(self):
  h,m=build({"sport":"nhl","date":"2026-10-26","events":[{"away_team":"BOS","home_team":"TOR",
   "start_utc":"2026-10-27T00:00:00Z","statistical_p_home":.6}]})
  self.assertIn("60.0%",h)
  self.assertIn("40.0%",m)
 def test_xss_escaped(self):
  h,_=build({"sport":"nhl","events":[{"away_team":"<script>alert(1)</script>","home_team":"TOR","statistical_p_home":None}]})
  self.assertNotIn("<script>alert(1)</script>",h)
 def test_nba(self):
  h,_=build({"sport":"nba","games":[{"away_team":"CHI","home_team":"BOS","statistical_baseline_home":.55}]})
  self.assertIn("55.0%",h)
 def test_bad_prob(self):
  with self.assertRaises(ValueError):
   build({"sport":"nhl","events":[{"away_team":"BOS","home_team":"TOR","statistical_p_home":2}]})
if __name__=="__main__":unittest.main()
