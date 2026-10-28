import json,tempfile,unittest
from pathlib import Path
from nhl.prior_game_evidence import generate
class PriorGameEvidenceTests(unittest.TestCase):
 def test_excludes_same_day_and_future(self):
  with tempfile.TemporaryDirectory() as td:
   def write(i,d,home,away):
    x={"game_id":i,"date":d,"home":home,"away":away,"boxscore":{"player_by_game_stats":{"homeTeam":{"goalies":[{"id":5}],"forwards":[{"id":6}]},"awayTeam":{"goalies":[{"id":7}]}}}}
    (Path(td)/(i+".json")).write_text(json.dumps(x))
   write("1","2025-10-01","BOS","MTL")
   write("2","2025-10-01","BOS","TOR")
   write("3","2025-10-03","BOS","MTL")
   records,summary=generate(td,3)
   self.assertEqual(records[0]["home"]["prior_games"],0)
   self.assertEqual(records[1]["home"]["prior_games"],0)
   self.assertEqual(records[2]["home"]["prior_games"],2)
   self.assertEqual(records[2]["home"]["prior_goalie_observation_games"],2)
   self.assertFalse(records[2]["same_game_starter_confirmed"])
   self.assertEqual(summary["games"],3)
 def test_missing_roster_does_not_become_confirmed(self):
  with tempfile.TemporaryDirectory() as td:
   for idx,day in enumerate(["2025-10-01","2025-10-03"]):
    (Path(td)/(str(idx)+".json")).write_text(json.dumps({"game_id":str(idx),"date":day,"home":"A","away":"B","boxscore":{}}))
   records,report=generate(td,2)
   self.assertEqual(records[1]["home"]["prior_roster_observation_games"],0)
   self.assertEqual(report["same_game_roster_confirmed"],0)
if __name__=="__main__":unittest.main()
