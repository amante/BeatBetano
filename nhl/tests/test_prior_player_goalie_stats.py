import json,tempfile,unittest
from pathlib import Path
from nhl.prior_player_goalie_stats import derive,extract
class HistoricalStats(unittest.TestCase):
 def game(self,i,date):
  return {"game_id":i,"date":date,"home":"BOS","away":"MTL",
   "boxscore":{"player_by_game_stats":{
    "homeTeam":{"goalies":[{"saves":27,"shotsAgainst":30}],"forwards":[{"goals":2,"shots":4}]},
    "awayTeam":{"goalies":[{"saves":24,"shotsAgainst":27}],"forwards":[{"goals":1,"shots":3}]}}}}
 def test_strict_prior_date_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   for i,d in [("1","2025-10-01"),("2","2025-10-01"),("3","2025-10-03")]:
    (Path(tmp)/(i+".json")).write_text(json.dumps(self.game(i,d)))
   rows,summary=derive(tmp,3)
   self.assertIsNone(rows[0]["home"]["prior_goalie_save_pct"])
   self.assertIsNone(rows[1]["home"]["prior_goalie_save_pct"])
   self.assertEqual(rows[2]["home"]["prior_goalie_save_pct"],.9)
   self.assertEqual(rows[2]["home"]["prior_skater_goals_per_observed_game"],2.)
   self.assertEqual(rows[2]["home"]["past_games"],2)
   self.assertFalse(rows[2]["home"]["pregame_starter_confirmed"])
   self.assertEqual(summary["same_game_rosters_verified"],0)
 def test_incomplete_invalid_stat_not_imputed(self):
  e=extract({"homeTeam":{"goalies":[{"saves":30,"shotsAgainst":20}],"forwards":[{"goals":3,"shots":1}]}},"home")
  self.assertIsNone(e["goalies"])
  self.assertIsNone(e["skaters"])
if __name__=="__main__":unittest.main()
