import json,tempfile,unittest
from pathlib import Path
from nhl.rolling_goalie_features import derive
class RollingGoalieTests(unittest.TestCase):
 def test_same_day_holdback_and_shrinkage(self):
  with tempfile.TemporaryDirectory() as tmp:
   for i,d in [("1","2025-10-01"),("2","2025-10-01"),("3","2025-10-03")]:
    obj={"game_id":i,"date":d,"home":"BOS","away":"TOR",
      "boxscore":{"player_by_game_stats":{"homeTeam":{"goalies":[{"saveShotsAgainst":"27/30"}]},
      "awayTeam":{"goalies":[{"saveShotsAgainst":"24/30"}]}}}}
    (Path(tmp)/(i+".json")).write_text(json.dumps(obj))
   rows,meta=derive(tmp,expected=3)
   self.assertIsNone(rows[0]["home"]["goalie_last_3"]["save_pct"])
   self.assertIsNone(rows[1]["home"]["goalie_last_3"]["save_pct"])
   x=rows[2]["home"]["goalie_last_3"]
   self.assertEqual(x["observed_games"],2)
   self.assertEqual(x["shots_against"],60)
   self.assertEqual(x["save_pct"],.9)
   self.assertAlmostEqual(x["shrunk_save_pct"],.903125)
   self.assertTrue(meta["no_same_day_outcome_features"])
if __name__=="__main__":unittest.main()
