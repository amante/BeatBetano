import unittest
from nhl.pulso_collective_calibration import run
from nhl.historical_target_walkforward import timeline
class TestCollectiveCalibration(unittest.TestCase):
 def rows(self):
  rows=[]
  for i in range(280):
   from datetime import date,timedelta
   day=(date(2025,10,1)+timedelta(days=i)).isoformat()
   rows.append({"game_id":str(i),"date":day,"home":"EDM","away":"COL",
     "ml_winner":"home" if i%3 else "away",
     "rt_result":("home","draw","away")[i%3],
     "first_to_plus3":("home","away","None")[i%3],
     "home_reached_plus3":"True" if i%3==0 else "False",
     "away_reached_plus3":"True" if i%3==1 else "False"})
  return rows
 def test_no_future_data_changes_past(self):
  rows=self.rows()
  first=timeline(rows,20,.5)
  rows[-1]["ml_winner"]="away" if rows[-1]["ml_winner"]=="home" else "home"
  second=timeline(rows,20,.5)
  self.assertEqual(first[-1]["probs"],second[-1]["probs"])
 def test_duplicate_fixture_rejected(self):
  rows=self.rows()
  with self.assertRaisesRegex(ValueError,"Duplicate"):run(rows+[dict(rows[-1])])
 def test_holdout_and_nonpromotion(self):
  rows=self.rows()
  result=run(rows)
  self.assertGreaterEqual(result["test_n"],100)
  self.assertFalse(result["automatic_promotion"])
  self.assertFalse(result["official_nhl_model"])
  self.assertEqual(result["pregame_feature_coverage"]["goalie_asof"],0)
if __name__=="__main__":unittest.main()
