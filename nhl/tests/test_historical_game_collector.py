import sys, unittest, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from historical_game_collector import extract,run
class HistoricalDetailTests(unittest.TestCase):
 def test_goal_path_and_postgame_warning(self):
  game={"id":"123","date":"2025-10-01","home":"BOS","away":"MTL","hg":4,"ag":2}
  box={"gameState":"OFF","gameType":2,"homeTeam":{"id":6},"awayTeam":{"id":3},
       "playerByGameStats":{"homeTeam":{"forwards":[]},"awayTeam":{"forwards":[]}}}
  pbp={"plays":[{"typeDescKey":"goal","eventId":2,"periodDescriptor":{"number":1,"periodType":"REG"},
    "timeInPeriod":"06:00","details":{"eventOwnerTeamId":6,"xCoord":90,"yCoord":2,"shotType":"wrist","situationCode":"1551"},"homeScore":1,"awayScore":0},
    {"typeDescKey":"shot-on-goal","eventId":3,"timeInPeriod":"07:00","details":{"eventOwnerTeamId":3,"xCoord":-75,"yCoord":8,"shotType":"snap","situationCode":"1551"}}]}
  r=extract(game,box,pbp)
  self.assertEqual(r["goal_events"][0]["home_score"],1)
  self.assertEqual(r["opponent_style_features_version"],1)
  self.assertEqual(r["opponent_style_shot_event_count"],2)
  self.assertEqual(r["opponent_style_profile"]["team_profiles"]["BOS"]["attack"]["goals"],1)
  self.assertIn("POSTGAME",r["point_in_time_warning"])
 def test_empty_goal_events_unusable(self):
  r=extract({"id":"1","date":"2025-10-01","home":"BOS","away":"MTL","hg":2,"ag":1},
            {"homeTeam":{"id":6},"awayTeam":{"id":3},"playerByGameStats":{}},{"plays":[]})
  self.assertFalse(r["goal_events_available"])
if __name__=="__main__":unittest.main()
