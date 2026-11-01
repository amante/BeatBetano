import unittest
from nhl.pulso_research_presentation_275 import present
class Presentation275(unittest.TestCase):
 def source(self):
  m={"ml":{"home":.54,"away":.46},"rt":{"home":.42,"draw":.2,"away":.38},
     "home3":{"yes":.3,"no":.7},"away3":{"yes":.27,"no":.73},
     "first3":{"home":.2,"away":.15,"none":.65}}
  return {"kind":"nhl_daily_complete_slate_274","date":"2026-11-01","official":False,"odds_used":False,
   "schedule_source_url":"https://api-web.nhle.com/v1/score/2026-11-01",
   "official_schedule_games":2,"experimental_predicted_games":1,
   "games":[{"game_id":"1","home":"CAR","away":"WPG","start_utc":"2026-11-01T18:00:00Z",
     "forecast_status":"experimental_forecast","markets":m,"official":False,"goalie_conditioned":False},
    {"game_id":"2","home":"NYR","away":"EDM","start_utc":"2026-11-01T23:00:00Z",
     "forecast_status":"pregame_forecast_unavailable","markets":None,"official":False,"goalie_conditioned":False}]}
 def test_all_games_and_all_markets(self):
  p=present(self.source())
  self.assertEqual(len(p["games"]),2)
  self.assertEqual(p["games"][0]["home_plus3"],.3)
  self.assertEqual(p["games"][0]["away_plus3"],.27)
  self.assertEqual(p["games"][0]["first_to_plus3"]["none"],.65)
  self.assertIsNone(p["games"][1]["ml"])
  self.assertIsNone(p["games"][0]["goalie_A_vs_B_probabilities"])
 def test_missing_market_fails(self):
  s=self.source();del s["games"][0]["markets"]["first3"]
  with self.assertRaises(ValueError):present(s)
 def test_wrong_market_sum_fails(self):
  s=self.source();s["games"][0]["markets"]["ml"]["home"]=.9
  with self.assertRaises(ValueError):present(s)
 def test_wrong_count_fails(self):
  s=self.source();s["official_schedule_games"]=1
  with self.assertRaises(ValueError):present(s)
if __name__=="__main__":unittest.main()
