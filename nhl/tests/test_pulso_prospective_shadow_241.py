import unittest
from nhl.pulso_prospective_shadow_241 import forecast,prior_features,MODEL_RUN_ID
class ProspectiveShadow241(unittest.TestCase):
 def setUp(self):
  self.games=[]
  for i in range(6):
   self.games.append({"game_id":str(2025020001+i),"date":"2026-01-%02d"%(i+1),
    "home":"BOS","away":"MTL","boxscore":{"player_by_game_stats":{
     "homeTeam":{"goalies":[{"saveShotsAgainst":"27/30"}],"forwards":[{"goals":2,"sog":4}]},
     "awayTeam":{"goalies":[{"saveShotsAgainst":"28/30"}],"forwards":[{"goals":1,"sog":4}]}}}})
  self.model={"status":"research_only_challenger_fitted","promoted":False,
    "training_end":"2026-02-01",
    "model":{"features":["team_prior_goalie_sv_diff","team_prior_skater_goals_diff"],
             "training_games":2182,"means":[0,0],"scales":[1,1],
             "weights":[1,1],"bias":0}}
  self.fixture={"game_id":"2026020101","home":"BOS","away":"MTL",
    "scheduled_start":"2026-04-01T23:00:00Z","game_state":"FUT"}
 def test_shadow_ml_generated(self):
  r=forecast([self.fixture],self.games,self.model,"2026-04-01T12:00:00Z")
  self.assertEqual(r["published_forecast_count"],1)
  self.assertFalse(r["auto_promoted"])
  self.assertEqual(r["games"][0]["model_version"],"team-ml-challenger-v0-run-"+str(MODEL_RUN_ID))
 def test_stale_data_blocks(self):
  self.fixture["scheduled_start"]="2026-12-01T23:00:00Z"
  x=forecast([self.fixture],self.games,self.model,"2026-12-01T12:00:00Z")
  self.assertEqual(x["published_forecast_count"],0)
  self.assertIn("BOS:stale_history",x["games"][0]["blockers"])
 def test_post_start_no_forecast(self):
  x=forecast([self.fixture],self.games,self.model,"2026-04-02T00:00:00Z")
  self.assertFalse(x["games"])
 def test_training_date_future_rejected(self):
  self.model["training_end"]="2027-01-01"
  with self.assertRaises(ValueError):forecast([self.fixture],self.games,self.model,"2026-04-01T12:00:00Z")
 def test_thin_history_blocks(self):
  x=forecast([self.fixture],self.games[:2],self.model,"2026-04-01T12:00:00Z")
  self.assertEqual(x["published_forecast_count"],0)
 def test_no_current_day_leakage(self):
  self.games.append({**self.games[-1],"game_id":"2026020300","date":"2026-04-01"})
  x=prior_features(self.games,"2026-04-01")
  self.assertEqual(x["BOS"]["features"]["past_games"],6)
if __name__=="__main__":unittest.main()
