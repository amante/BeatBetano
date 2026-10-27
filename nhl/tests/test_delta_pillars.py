import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from delta_pillars import feature_sheet
class TestPillars(unittest.TestCase):
 def snapshot(self):
  teams=[{"teamFullName":"Anaheim Ducks","teamId":24,"gamesPlayed":3,
   "goalsForPerGame":3.5,"goalsAgainstPerGame":2.0,"powerPlayPct":0.2,"penaltyKillPct":0.8}]
  return {"sport":"nhl","season":"20262027","as_of_utc":"2026-10-27T12:00:00+00:00",
  "reports":{"skater/summary":[{"playerId":1,"teamAbbrevs":"ANA","positionCode":"D","points":2,"goals":1},
  {"playerId":2,"teamAbbrevs":"ANA","positionCode":"C","points":4,"goals":2}],
  "goalie/summary":[{"playerId":3,"teamAbbrevs":"ANA","saves":100,"shotsAgainst":110,"savePct":0.909}],
  "team/summary":teams}}
 def test_incomplete_teams_rejected(self):
  with self.assertRaisesRegex(ValueError,"Incomplete"):feature_sheet(self.snapshot())
 def test_no_probabilities_or_invented_ratings(self):
  s=self.snapshot()
  # Complete 32-team list using a deliberately repeated team is not valid
  # for model evaluation; the sheet should still never invent a rating.
  s["reports"]["team/summary"]=s["reports"]["team/summary"]*32
  result=feature_sheet(s)
  team=result["teams"]["ANA"]
  self.assertIsNone(team["crs_evidence"]["rating"])
  self.assertIsNone(team["unit_evidence"]["rating"])
  self.assertIsNone(team["goalie_evidence"]["goalie_daily_rating"])
  self.assertFalse(result["calibrated"])
if __name__=="__main__":unittest.main()
