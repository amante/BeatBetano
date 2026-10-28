import json,tempfile,unittest
from pathlib import Path
from nhl.official_roster_snapshot import parse_roster
from nhl.individual_goalie_toi_history import seconds,goalie_totals,derive
class NHLOfficialSourceTests(unittest.TestCase):
 def test_current_roster_not_game_lineup(self):
  x=parse_roster({"forwards":[{"id":101,"positionCode":"C"}],
                  "defensemen":[{"id":202,"positionCode":"D"}],
                  "goalies":[{"id":303,"positionCode":"G"}]},
                 "BOS","2026-10-28T12:00:00Z")
  self.assertFalse(x["goalie_starter_confirmed"])
  self.assertTrue(all(p["lineup_status"]=="unknown" for p in x["players"]))
  self.assertIsNone(x["players"][0]["expected_share"])
 def test_field_parsers(self):
  self.assertEqual(seconds("12:35"),755)
  self.assertIsNone(seconds("12:92"))
  self.assertEqual(goalie_totals({"saveShotsAgainst":"27/30"}),(27,30))
  self.assertIsNone(goalie_totals({"saveShotsAgainst":"45/30"}))
 def test_no_same_day_player_metric_leakage(self):
  with tempfile.TemporaryDirectory() as tmp:
   for gid,date in (("1","2025-10-01"),("2","2025-10-01"),("3","2025-10-03")):
    game={"game_id":gid,"date":date,"home":"BOS","away":"MTL",
      "boxscore":{"player_by_game_stats":{"homeTeam":{
        "goalies":[{"playerId":303,"saveShotsAgainst":"27/30","toi":"60:00"}],
        "forwards":[{"playerId":101,"goals":1,"sog":3,"toi":"19:30"}]}}}}
    (Path(tmp)/(gid+".json")).write_text(json.dumps(game))
   rows,report=derive(tmp,3)
   self.assertEqual(rows[0]["home"]["players"],{})
   self.assertEqual(rows[1]["home"]["players"],{})
   self.assertEqual(rows[2]["home"]["players"]["303"]["goalie_shots"],60)
   self.assertEqual(rows[2]["home"]["players"]["101"]["toi_seconds"],2340)
   self.assertEqual(report["games"],3)
if __name__=="__main__":unittest.main()
