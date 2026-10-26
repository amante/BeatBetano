import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from possession_intelligence import build,lineup_confirmed,extract
GAME={"game_id":"100","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-10-20T20:00:00Z"}
def payload():
 def t(team,pts):
  return {"team":{"abbreviation":team},"statistics":[{"name":k,"displayValue":str(v)} for k,v in {"fieldGoalsAttempted":88,"freeThrowsAttempted":20,"offensiveRebounds":10,"turnovers":12,"points":pts}.items()]}
 return {"header":{"competitions":[{"id":"100","status":{"type":{"completed":True}}}]},"boxscore":{"teams":[t("BOS",110),t("NYK",105)]}}
class Tests(unittest.TestCase):
 def test_estimated_possessions(self):
  p=extract(payload(),GAME)
  self.assertAlmostEqual(p["BOS"]["possessions_estimated"],98.8)
 def test_unconfirmed_lineups_never_mislabeled(self):
  tip="2026-10-21T20:00:00Z"
  x={"team":"BOS","starters":["a","b","c","d","e"],"source_url":"https://example.org","observed_at_utc":"2026-10-21T18:00:00Z","is_confirmed":True}
  self.assertEqual(len(lineup_confirmed(x,tip,"BOS")),5)
  self.assertEqual(lineup_confirmed({**x,"is_confirmed":False},tip,"BOS"),[])
  self.assertEqual(lineup_confirmed({**x,"observed_at_utc":"2026-10-22T18:00:00Z"},tip,"BOS"),[])
 def test_no_invented_scoring_rate(self):
  sample={"postgame_history_only":True,"games":[]}
  future={"content_sha256":"abc","predictions":[{"game_id":"f","tipoff_utc":"2026-10-21T20:00:00Z","home_team":"BOS","away_team":"NYK"}]}
  r=build(future,[],sample)
  self.assertIsNone(r["games"]["f"]["teams"]["BOS"]["scoring_possession_rate_pct"])
  self.assertIsNone(r["games"]["f"]["projections"]["BOS"]["possessions_projected"])
if __name__=="__main__":unittest.main()
