import json,tempfile,unittest
from pathlib import Path
from nhl.roster_aware_foundation import snapshots,score_expected_roster
class RosterEngineContractTests(unittest.TestCase):
 def test_same_day_holdout_and_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   for id,date in (("1","2025-10-01"),("2","2025-10-01"),("3","2025-10-03")):
    g={"game_id":id,"date":date,"home":"BOS","away":"MTL",
       "boxscore":{"player_by_game_stats":{"homeTeam":{"forwards":[{"playerId":101,"goals":1,"sog":3}]},
                     "awayTeam":{"goalies":[{"playerId":202}]}}}}
    (Path(tmp)/(id+".json")).write_text(json.dumps(g))
   rows,report=snapshots(tmp,3)
   self.assertEqual(rows[0]["home"]["players"],{})
   self.assertEqual(rows[1]["home"]["players"],{})
   self.assertEqual(rows[2]["home"]["players"]["101"]["appearances"],2)
   self.assertEqual(report["games"],3)
   lineup={"as_of":"2025-10-03T12:00:00Z","source":"verified-source",
     "players":[{"player_id":101,"weight":1,"status":"projected"},{"player_id":999,"weight":1,"status":"projected"}]}
   s=score_expected_roster(rows[2]["home"],lineup,"2025-10-03T19:00:00Z")
   self.assertEqual(s["score_goals_per_observed_player_game"],1.)
   self.assertEqual(s["missing_player_ids"],["999"])
   with self.assertRaises(ValueError):
    score_expected_roster(rows[2]["home"],dict(lineup,as_of="2025-10-04T12:00:00Z"),"2025-10-03T19:00:00Z")
if __name__=="__main__":unittest.main()
