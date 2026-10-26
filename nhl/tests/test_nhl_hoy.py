import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nhl_hoy import slate
S={"games":[{"id":1,"gameType":2,"gameState":"FUT","startTimeUTC":"2026-10-27T00:00:00Z",
"homeTeam":{"abbrev":"TOR"},"awayTeam":{"abbrev":"BOS"}}]}
R={"standings":[{"teamAbbrev":{"default":"TOR"},"gamesPlayed":5,"goalDifferential":4},
                {"teamAbbrev":{"default":"BOS"},"gamesPlayed":5,"goalDifferential":-2}]}
class Tests(unittest.TestCase):
 def test_candidate_never_final(self):
  x=slate(S,R,"2026-10-26T12:00:00Z","2026-10-26")["events"][0]
  self.assertGreater(x["statistical_p_home"],.5)
  self.assertIsNone(x["final_probability"])
  self.assertIsNone(x["three_goal_lead_home"])
 def test_missing_standings_fail_closed(self):
  x=slate(S,{"standings":[]},"2026-10-26T12:00:00Z","2026-10-26")
  self.assertIsNone(x["events"][0]["statistical_p_home"])
 def test_started_filtered(self):
  t={"games":[dict(S["games"][0],gameState="LIVE")]}
  self.assertEqual(slate(t,R,"2026-10-26T12:00:00Z","2026-10-26")["events"],[])
 def test_past_not_retrospective(self):
  with self.assertRaises(ValueError):slate(S,R,"2026-10-26T12:00:00Z","2026-10-24")
if __name__=="__main__":unittest.main()
