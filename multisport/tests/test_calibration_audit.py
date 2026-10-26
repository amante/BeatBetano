import unittest
from multisport.calibration_audit import audit
def row(i,year=2025,sport="nhl",market="moneyline"):
 return {"game_id":str(i),"sport":sport,"market":market,"model_version":"candidate-1",
 "training_dataset_hash":"frozen-hash","prediction_as_of_utc":f"{year-1}-10-01T10:00:00Z",
 "tipoff_utc":f"{year-1}-10-01T20:00:00Z",
 "latest_feature_observed_at_utc":f"{year-1}-10-01T09:00:00Z",
 "training_cutoff_utc":f"{year-1}-09-30T00:00:00Z",
 "point_in_time_sources_verified":True,"market_odds_used":False,
 "season_end_year":year,"baseline_p":.6,"challenger_p":.55,"outcome":1}
class Test(unittest.TestCase):
 def test_two_seasons_descriptive_only(self):
  r=audit([row(1),row(2,2026)],"nhl",min_games_per_season=1)
  self.assertTrue(r["at_least_two_holdout_seasons"])
  self.assertFalse(r["independent_validation_passed"])
  self.assertEqual(len(r["by_season"]),2)
 def test_future_data_rejected(self):
  a=row(1);a["latest_feature_observed_at_utc"]="2024-10-01T21:00:00Z"
  with self.assertRaises(ValueError):audit([a],"nhl",min_games_per_season=1)
 def test_mix_markets_rejected(self):
  with self.assertRaises(ValueError):audit([row(1,market="regulation_home")],"nhl",min_games_per_season=1)
 def test_unverified_refused(self):
  a=row(1);a["point_in_time_sources_verified"]=False
  with self.assertRaises(ValueError):audit([a],"nhl",min_games_per_season=1)
 def test_nba_market(self):
  x=audit([row(1,sport="nba")],"nba",min_games_per_season=1)
  self.assertEqual(x["sport"],"nba")
if __name__=="__main__":unittest.main()
