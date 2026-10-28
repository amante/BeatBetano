import json,tempfile,unittest
from pathlib import Path
from nhl.official_roster_snapshot import TEAMS
from nhl.current_roster_history_coverage import coverage
class CoverageTests(unittest.TestCase):
 def test_cross_team_history_and_same_day_freeze(self):
  with tempfile.TemporaryDirectory() as d:
   for gid,day in (("1","2026-10-26"),("2","2026-10-28")):
    g={"game_id":gid,"date":day,"home":"TOR","away":"BOS",
      "boxscore":{"player_by_game_stats":{"homeTeam":{"forwards":[{"playerId":101,"goals":1,"sog":3,"toi":"12:00"}]}}}}
    (Path(d)/(gid+".json")).write_text(json.dumps(g))
   roster=[]
   for i,t in enumerate(TEAMS):
    roster.append({"team":t,"source_kind":"official_current_team_roster_not_match_lineup",
       "source_url":"https://api-web.nhle.com/v1/roster/"+t+"/current","as_of":"2026-10-28T13:00:00Z",
       "players":[{"player_id":101 if t=="BOS" else 1000+i,
                   "position_group":"skater","lineup_status":"unknown"}]})
   x=coverage(roster,d,2,min_games=1)
   bos=next(x for x in x["teams"] if x["team"]=="BOS")
   self.assertEqual(bos["players"][0]["history_category"],"other_team_only")
   self.assertEqual(bos["players"][0]["prior_games_all_teams"],1)
   self.assertEqual(x["historical_games_considered"],1)
   self.assertEqual(x["lineups_confirmed"],0)
   self.assertEqual(x["total"]["roster_players"],32)
 def test_incomplete_team_set_fails_closed(self):
  with self.assertRaisesRegex(ValueError,"32"):
   coverage([], ".",0)
if __name__=="__main__":unittest.main()
