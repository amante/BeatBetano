import unittest
from nhl.pulso_goalie_daily_253 import evaluate
class GoalieDaily253(unittest.TestCase):
 def fixture(self):
  return {"kind":"nhl_candidate_goalie_history_251","official_predictions":0,
   "as_of_utc":"2026-10-31T16:00:00Z","games":[{
    "game_id":"1","home":"BOS","away":"MTL","teams":{
     "BOS":{"nhl_player_id":123,"source_goalie_status":"source_reported_confirmed",
       "status":"observed","metrics":{"season_to_date":{"games":10,"saves":275,"shots_against":300},
        "last_5_games":{"games":5,"saves":135,"shots_against":150},"last_game_date":"2026-10-29"}},
     "MTL":{"nhl_player_id":456,"source_goalie_status":"unverified","status":"no_prior_games"}}}]}
 def test_observed_index_without_ml(self):
  x=evaluate(self.fixture())
  a=x["games"][0]["teams"]["BOS"]
  self.assertEqual(x["observed_sides"],1)
  self.assertEqual(a["season_sv_pct"],round(275/300,6))
  self.assertEqual(a["shrunk_sv_pct"],round((275+200*.9)/500,6))
  self.assertEqual(a["days_since_last_appearance"],2)
  self.assertIsNone(a["goalie_daily_rating"])
  self.assertIsNone(a["ml_delta"])
  self.assertEqual(a["starter_status"],"not_independently_confirmed")
 def test_missing_history_fails_closed(self):
  x=evaluate(self.fixture())
  self.assertEqual(x["games"][0]["teams"]["MTL"]["status"],"blocked")
 def test_postcutoff_appearance_rejected(self):
  x=self.fixture();x["games"][0]["teams"]["BOS"]["metrics"]["last_game_date"]="2026-10-31"
  with self.assertRaises(ValueError):evaluate(x)
 def test_invalid_saves_rejected(self):
  x=self.fixture();x["games"][0]["teams"]["BOS"]["metrics"]["season_to_date"]["saves"]=301
  with self.assertRaises(ValueError):evaluate(x)
 def test_not_official(self):
  x=self.fixture();x["official_predictions"]=1
  with self.assertRaises(ValueError):evaluate(x)
if __name__=="__main__":unittest.main()
