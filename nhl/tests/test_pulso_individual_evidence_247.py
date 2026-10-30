import unittest
from nhl.pulso_individual_evidence_247 import evaluate_fixture
from nhl.pulso_sporting_core_245 import integrate
class Individual247(unittest.TestCase):
 def setUp(self):
  self.r={"data_kind":"source_readiness_only","official_predictions":0,
   "generated_at_utc":"2026-10-30T16:00:00Z",
   "games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-10-30T23:00:00Z"}]}
 def test_empty_package_reports_blockers_and_no_forecast(self):
  x=evaluate_fixture(self.r,{})
  self.assertEqual(x["official_predictions"],0)
  self.assertEqual(x["games"][0]["teams"]["BOS"]["status"],"blocked")
  self.assertFalse(x["games"][0]["applied_to_ml"])
 def test_roster_cannot_be_substituted_for_lineup(self):
  p={"history":{"team":"BOS","date":"2026-10-29","players":{}},
   "baseline_lineup":{"lineup_type":"roster","source":"official","as_of":"2026-10-30T14:00:00Z"},
   "expected_lineup":{"lineup_type":"roster","source":"official","as_of":"2026-10-30T14:00:00Z"}}
  with self.assertRaises(ValueError):evaluate_fixture(self.r,{"1":{"BOS":p}})
 def test_future_lineup_rejected(self):
  p={"history":{"team":"BOS","date":"2026-10-29","players":{}},
   "baseline_lineup":{"lineup_type":"projected","source":"nhl","as_of":"2026-10-30T19:00:00Z"},
   "expected_lineup":{"lineup_type":"projected","source":"nhl","as_of":"2026-10-30T14:00:00Z"}}
  with self.assertRaises(ValueError):evaluate_fixture(self.r,{"1":{"BOS":p}})
 def test_team_history_cutoff_rejected(self):
  p={"history":{"team":"BOS","date":"2026-10-30","players":{}},
   "baseline_lineup":{"lineup_type":"projected","source":"nhl","as_of":"2026-10-30T14:00:00Z"},
   "expected_lineup":{"lineup_type":"projected","source":"nhl","as_of":"2026-10-30T14:00:00Z"}}
  with self.assertRaises(ValueError):evaluate_fixture(self.r,{"1":{"BOS":p}})
 def test_manifest_preserves_blockers(self):
  individual=evaluate_fixture(self.r,{})
  stamp=self.r["generated_at_utc"]
  bridge={"kind":"sporting_source_bridge","as_of":stamp,"games":{"1":{
   "game_id":"1","home":"BOS","away":"MTL","start_utc":self.r["games"][0]["start_utc"],"as_of":stamp,
   "teams":{t:{"roster_identity_available":False,"provider_goalie_id_observed":None,
     "goalie_confirmed_independently":False} for t in ("BOS","MTL")}}}}
  x=integrate(self.r,bridge,{},individual_evidence=individual)
  self.assertEqual(x["games"][0]["teams"]["BOS"]["individual_player_goalie_evidence"]["status"],"blocked")
  self.assertIsNone(x["games"][0]["sporting_probabilities"])
if __name__=="__main__":unittest.main()
