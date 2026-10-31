import unittest
from nhl.pulso_goalie_states_255 import classify
class GoalieStates255(unittest.TestCase):
 def fixture(self):
  report={"generated_at_utc":"2026-10-31T14:00:00Z","games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-10-31T22:00:00Z"}]}
  identity={"kind":"nhl_fixture_identity_gate_248","as_of_utc":report["generated_at_utc"],"games":[{"game_id":"1","home":"BOS","away":"MTL","teams":{
   "BOS":{"source_goalie_player_id":123,"source_goalie_status":"source_reported_confirmed","independent_goalie_confirmation":False,"blockers":["goalie_not_independently_confirmed"]},
   "MTL":{"source_goalie_player_id":None,"source_goalie_status":"unverified","independent_goalie_confirmation":False,"blockers":["no_unique_fixture_linked_goalie_player_id"]}}}]}
  return report,identity
 def test_unconfirmed_is_normal(self):
  a,b=self.fixture();x=classify(a,b)
  self.assertEqual(x["counts"]["probable"],1)
  self.assertEqual(x["counts"]["unconfirmed"],1)
  for row in x["games"][0]["teams"].values():
   self.assertTrue(row["normal_pregame_uncertainty"])
   self.assertFalse(row["auto_pass"])
   self.assertIsNone(row["ml_penalty"])
 def test_independent_confirmation(self):
  a,b=self.fixture();b["games"][0]["teams"]["BOS"]["independent_goalie_confirmation"]=True
  x=classify(a,b)
  self.assertEqual(x["counts"]["confirmed"],1)
 def test_provider_assertion_not_confirmed(self):
  a,b=self.fixture();x=classify(a,b)
  self.assertEqual(x["games"][0]["teams"]["BOS"]["state"],"probable")
 def test_puck_drop_guard(self):
  a,b=self.fixture();a["generated_at_utc"]="2026-10-31T22:00:00Z";b["as_of_utc"]=a["generated_at_utc"]
  with self.assertRaises(ValueError):classify(a,b)
 def test_wrong_fixture(self):
  a,b=self.fixture();b["games"][0]["away"]="TOR"
  with self.assertRaises(ValueError):classify(a,b)
if __name__=="__main__":unittest.main()
