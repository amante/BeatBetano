import json,tempfile,unittest
from pathlib import Path
from nhl.historical_feature_readiness import audit,inspect

class ReadinessTests(unittest.TestCase):
 def game(self,gid,stats=None):
  return {"game_id":gid,"boxscore":{"home_team":{"id":1},"away_team":{"id":2},
          "player_by_game_stats":stats}}
 def test_postgame_does_not_confirm_starter_or_roster(self):
  x=inspect(self.game("1",{"homeTeam":{"goalies":[{"playerId":7}]},"awayTeam":{"forwards":[1]}}))
  self.assertTrue(x["goalie_postgame_appearances"])
  self.assertTrue(x["roster_postgame_appearances"])
  self.assertFalse(x["confirmed_starter_at_tipoff"])
  self.assertFalse(x["dated_roster_at_tipoff"])
  self.assertFalse(x["dated_pp_pk_at_tipoff"])
 def test_missing_stats_not_inferred(self):
  x=inspect(self.game("1"))
  self.assertFalse(x["goalie_postgame_appearances"])
  self.assertFalse(x["roster_postgame_appearances"])
 def test_audit_coverage_and_identity(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   (p/"1.json").write_text(json.dumps(self.game("1",{"homeTeam":{"goalies":[1]}})))
   a=audit(td,1)
   self.assertEqual(a["games"],1)
   self.assertEqual(a["module_readiness"]["goalie"]["same_game_confirmed_starters_verified"],0)
   with self.assertRaisesRegex(ValueError,"Expected 2"):audit(td,2)
if __name__=="__main__":unittest.main()
