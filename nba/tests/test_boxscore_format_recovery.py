import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from possession_intelligence import extract
class Tests(unittest.TestCase):
 def test_made_attempted_espn_fields(self):
  game={"game_id":"a","home_team":"BOS","away_team":"NYK"}
  def team(code):
   return {"team":{"abbreviation":code},"statistics":[
    {"name":"fieldGoalsMade-fieldGoalsAttempted","displayValue":"40-90"},
    {"name":"freeThrowsMade-freeThrowsAttempted","displayValue":"15-20"},
    {"name":"offensiveRebounds","displayValue":"12"},
    {"name":"totalTurnovers","displayValue":"10"}]}
  source={"header":{"competitions":[{"id":"a","status":{"type":{"completed":True}},
   "competitors":[{"team":{"abbreviation":"BOS"},"score":"105"},
    {"team":{"abbreviation":"NYK"},"score":"108"}]}]},
   "boxscore":{"teams":[team("BOS"),team("NYK")]}}
  result=extract(source,game)
  self.assertAlmostEqual(result["BOS"]["possessions_estimated"],96.8)
 def test_missing_fields_explained(self):
  game={"game_id":"a","home_team":"BOS","away_team":"NYK"}
  source={"header":{"competitions":[{"id":"a","status":{"type":{"completed":True}}}]},
   "boxscore":{"teams":[{"team":{"abbreviation":"BOS"},"statistics":[]}]}}
  with self.assertRaisesRegex(ValueError,"Missing boxscore fields"):extract(source,game)
if __name__=="__main__":unittest.main()
