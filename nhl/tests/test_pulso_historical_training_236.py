import unittest
from nhl.pulso_historical_training_236 import build
class HistoricalTraining236(unittest.TestCase):
 def setUp(self):
  self.labels=[{"game_id":"2025020001","date":"2025-10-01","home":"BOS","away":"MTL",
    "ml_winner":"home","rt_result":"draw","home_reached_plus3":"False",
    "away_reached_plus3":"False","first_to_plus3":"",
    "data_class":"POSTGAME_LABELS_NOT_PREGAME_FEATURES"}]
  team={"past_games":2,"past_goalie_observation_games":2,"past_skater_observation_games":2,
        "prior_goalie_save_pct":.91,"prior_goalie_shots_against":44,
        "prior_skater_goals_per_observed_game":2.5,"prior_skater_shots_per_observed_game":29,
        "pregame_starter_confirmed":False,"pregame_roster_confirmed":False}
  self.history=[{"game_id":"2025020001","date":"2025-10-01",
   "source_class":"earlier_dates_postgame_boxscores_only","home":team.copy(),"away":team.copy()}]
 def test_join_and_separate_targets(self):
  x=build(self.history,self.labels,1)
  row=x["rows"][0]
  self.assertEqual(row["target"]["ml_winner"],"home")
  self.assertNotIn("ml_winner",row["features"]["home"])
  self.assertEqual(x["manifest"]["complete_core_feature_games"],1)
  self.assertFalse(x["manifest"]["model_promoted"])
 def test_incorrect_source_is_rejected(self):
  self.history[0]["source_class"]="same_game_postgame"
  with self.assertRaises(ValueError):build(self.history,self.labels)
 def test_date_mismatch_is_rejected(self):
  self.labels[0]["date"]="2025-10-02"
  with self.assertRaises(ValueError):build(self.history,self.labels)
 def test_identity_collision_rejected(self):
  with self.assertRaises(ValueError):build(self.history,self.labels*2)
 def test_invented_starting_goalie_rejected(self):
  self.history[0]["home"]["pregame_starter_confirmed"]=True
  with self.assertRaises(ValueError):build(self.history,self.labels)
 def test_missing_core_feature_is_visible(self):
  self.history[0]["home"]["prior_goalie_save_pct"]=None
  x=build(self.history,self.labels)
  self.assertEqual(x["manifest"]["complete_core_feature_games"],0)
if __name__=="__main__":unittest.main()
