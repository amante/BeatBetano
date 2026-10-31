import unittest
from nhl.pulso_goalie_scenarios_258 import build
class GoalieScenarios258(unittest.TestCase):
 def data(self):
  at="2026-10-31T14:00:00Z"
  report={"generated_at_utc":at,"games":[{"game_id":"1","home":"NSH","away":"BUF","start_utc":"2026-10-31T23:00:00Z"}]}
  identity={"kind":"nhl_fixture_identity_gate_248","as_of_utc":at,"games":[{"game_id":"1","home":"NSH","away":"BUF","teams":{"NSH":{"source_goalie_player_id":10,"source_goalie_name":"Goalie A"},"BUF":{"source_goalie_player_id":20,"source_goalie_name":"Goalie C"}}}]}
  external={"kind":"nhl_external_goalie_observations_257","as_of_utc":at,"observations":[{"game_id":"1","team":"NSH","player_id":11,"name":"Goalie B","provider_status":"likely"},{"game_id":"1","team":"BUF","player_id":21,"name":"Goalie D","provider_status":"confirmed"}]}
  return report,identity,external
 def test_four_pairings_without_fake_odds(self):
  result=build(*self.data())
  game=result["games"][0]
  self.assertEqual(game["scenario_count"],4)
  self.assertEqual({x["home_goalie"]["name"] for x in game["scenarios"]},{"Goalie A","Goalie B"})
  self.assertTrue(all(all(p is None for p in x["probabilities"].values()) for x in game["scenarios"]))
  self.assertTrue(all(not x["auto_pass"] for x in game["scenarios"]))
 def test_same_id_deduplicates(self):
  d=list(self.data());d[2]["observations"][0]["player_id"]=10
  self.assertEqual(build(*d)["games"][0]["scenario_count"],2)
 def test_unconfirmed_not_failure(self):
  d=list(self.data());d[2]["observations"]=[]
  self.assertEqual(build(*d)["games"][0]["scenario_count"],1)
 def test_fixture_mismatch_blocked(self):
  d=list(self.data());d[1]["games"][0]["home"]="TOR"
  with self.assertRaises(ValueError):build(*d)
if __name__=="__main__":unittest.main()
