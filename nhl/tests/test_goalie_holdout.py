import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_holdout import walk_forward
def row(i,year):
 return {"event_id":f"{year}-{i}","sport":"nhl","market":"moneyline","odds_used":False,
 "prediction_as_of_utc":f"{year}-01-01T12:00:00Z","tipoff_utc":f"{year}-01-01T23:00:00Z",
 "latest_feature_observed_at_utc":f"{year}-01-01T11:00:00Z","sources_verified":True,
 "starter_confirmed_at_freeze":True,"baseline_p_home":.52,"home_won":i%2,
 "goalie_sv_recent":.91+(i%3)/100,"goalie_starts_7d":i%4,
 "opponent_goal_diff_prior":i%5,"team_goal_diff_prior":i%6,
 "defense_goals_against_prior":2+(i%4)/5}
class Test(unittest.TestCase):
 def test_holdout_unapproved(self):
  x=walk_forward([row(i,y) for y in (2024,2025) for i in range(40)],min_train=30,min_test=20)
  self.assertEqual(len(x["holdout_results"]),1)
  self.assertFalse(x["authorized_for_final_probability"])
 def test_leakage_rejected(self):
  a=row(1,2025);a["latest_feature_observed_at_utc"]="2025-01-02T00:00:00Z"
  with self.assertRaises(ValueError):walk_forward([a])
 def test_unconfirmed_rejected(self):
  a=row(1,2025);a["starter_confirmed_at_freeze"]=False
  with self.assertRaises(ValueError):walk_forward([a])
if __name__=="__main__":unittest.main()
