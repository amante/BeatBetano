import unittest
from nhl.pulso_historical_team_join_228 import join
class History228(unittest.TestCase):
 def setUp(self):
  self.bridge={"kind":"sporting_source_bridge","games":{"2":{"home":"EDM","away":"CGY",
    "start_utc":"2026-10-30T00:00:00Z","as_of":"2026-10-29T20:00:00Z"}}}
  self.archive=[{"game_id":"2","date":"2026-10-30","source_class":"earlier_dates_postgame_boxscores_only",
    "home":{"prior_goalie_save_pct":.91,"prior_skater_goals_per_observed_game":3.1,"past_goalie_observation_games":10},
    "away":{"prior_goalie_save_pct":.89,"prior_skater_goals_per_observed_game":2.5,"past_goalie_observation_games":8}}]
  self.labels=[{"game_id":"2","date":"2026-10-30","home":"EDM","away":"CGY"}]
 def test_correct_prior_date_team_join(self):
  x=join(self.bridge,self.archive,self.labels)
  t=x["games"]["2"]["teams"]["EDM"]
  self.assertEqual(t["features"]["team_prior_goalie_save_pct"],.91)
  self.assertFalse(t["confirmed_starting_goalie"])
  self.assertFalse(x["full_model_ready"])
 def test_mismatched_identity_rejected(self):
  with self.assertRaises(ValueError):join(self.bridge,self.archive,[])
 def test_future_snapshot_not_attributed(self):
  self.archive[0]["date"]="2026-10-31";self.labels[0]["date"]="2026-10-31"
  self.assertIsNone(join(self.bridge,self.archive,self.labels)["games"]["2"]["teams"]["EDM"]["features"])
if __name__=="__main__":unittest.main()
