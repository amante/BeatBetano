import unittest
from nhl.research_features_187_190 import compile_features,safe_rate,TIER_A
class ResearchFeaturesTests(unittest.TestCase):
 def test_same_day_never_uses_own_result(self):
  games=[{"game_id":"a","date":"2026-10-01","home":"BOS","away":"MTL"},
   {"game_id":"b","date":"2026-10-01","home":"TOR","away":"OTT"},
   {"game_id":"c","date":"2026-10-03","home":"BOS","away":"TOR"}]
  obs={"a":{"home":{"pp_goals":1,"pp_chances":4,"pk_goals_allowed":0,"pk_chances":3},
   "away":{"pp_goals":0,"pp_chances":3,"pk_goals_allowed":1,"pk_chances":4}}}
  r=compile_features(games,obs)
  self.assertIsNone(r[0]["teams"]["BOS"]["pp"])
  self.assertIsNone(r[1]["teams"]["TOR"]["pp"])
  self.assertEqual(r[2]["teams"]["BOS"]["pp"]["opportunities"],4)
  self.assertEqual(r[2]["teams"]["BOS"]["rest_days"],1)
  self.assertEqual(r[2]["teams"]["TOR"]["rest_days"],1)
  self.assertEqual(r[0]["rivalry_tier"],"A")
  self.assertTrue(r[0]["division"])
  self.assertIsNone(r[0]["home_underdog"])
 def test_st_missing_or_invalid(self):
  self.assertIsNone(safe_rate(None,4))
  self.assertAlmostEqual(safe_rate(1,5)["posterior_mean"],.2)
  with self.assertRaises(ValueError):safe_rate(3,2)
 def test_no_market_based_underdog(self):
  r=compile_features([{"game_id":"x","date":"2026-10-01","home":"BOS","away":"CGY"}],{})
  self.assertIsNone(r[0]["home_underdog"])
  self.assertIsNone(r[0]["teams"]["BOS"]["back_to_back"])
if __name__=="__main__":unittest.main()
