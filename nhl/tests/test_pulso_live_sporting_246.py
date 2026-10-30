import unittest
from nhl.pulso_live_sporting_246 import build,HOST
from nhl.pulso_sporting_core_245 import integrate
class Live246(unittest.TestCase):
 def setUp(self):
  self.report={"data_kind":"source_readiness_only","official_predictions":0,"generated_at_utc":"2026-10-30T16:00:00Z","games":[{"game_id":"9","home":"BOS","away":"MTL","start_utc":"2026-10-31T01:00:00Z"}]}
  self.stats={"standings":[{"teamAbbrev":{"default":t},"gamesPlayed":10,"goalFor":30,"goalAgainst":25,"powerPlayPct":23.0,"penaltyKillPct":82.0} for t in ("BOS","MTL")]}
 def test_prior_day_no_official_promotion(self):
  x=build(self.report,self.stats,HOST+"2026-10-29")
  self.assertEqual(x["official_predictions"],0)
  self.assertEqual(x["prior_completed_day"],"2026-10-29")
  self.assertEqual(x["games"][0]["sides"]["BOS"]["features"]["goals_for_per_game"],3)
  self.assertFalse(x["games"][0]["applied_to_ml"])
 def test_wrong_day_is_rejected(self):
  with self.assertRaises(ValueError):build(self.report,self.stats,HOST+"2026-10-30")
 def test_missing_team_fails_closed(self):
  self.stats["standings"]=self.stats["standings"][:1]
  x=build(self.report,self.stats,HOST+"2026-10-29")
  self.assertEqual(x["games"][0]["sides"]["MTL"]["status"],"missing")
 def test_integrated_as_observed_not_applied(self):
  live=build(self.report,self.stats,HOST+"2026-10-29")
  at=self.report["generated_at_utc"]
  bridge={"kind":"sporting_source_bridge","as_of":at,"games":{"9":{"game_id":"9","home":"BOS","away":"MTL","start_utc":self.report["games"][0]["start_utc"],"as_of":at,
   "teams":{t:{"roster_identity_available":False,"provider_goalie_id_observed":None,"goalie_confirmed_independently":False} for t in ("BOS","MTL")}}}}
  x=integrate(self.report,bridge,{},live_sporting=live)
  g=x["games"][0]
  self.assertEqual(g["teams"]["BOS"]["official_prior_day_team_form"]["features"]["games_played"],10)
  self.assertIsNone(g["sporting_probabilities"])
  self.assertTrue(all(not m["applied_to_sporting_probability"] for m in g["module_manifest"].values()))
if __name__=="__main__":unittest.main()
