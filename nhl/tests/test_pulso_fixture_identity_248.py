import unittest
from nhl.pulso_fixture_identity_248 import reconcile,normalize
class FixtureIdentity248(unittest.TestCase):
 def setUp(self):
  self.report={"data_kind":"source_readiness_only","official_predictions":0,
    "generated_at_utc":"2026-10-30T14:00:00Z",
    "games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-10-30T22:00:00Z"}]}
  self.rosters={"rosters":[{"team":team,"as_of":"2026-10-30T13:00:00Z",
    "source_url":"https://api-web.nhle.com/v1/roster/"+team+"/current",
    "players":[{"player_id":i,"full_name":"Joe Goalie"}]} for i,team in [(123,"BOS"),(456,"MTL")]]}
  self.goalies={"observations":[{"game_id":"1","team":"BOS","nhl_player_id":123,
   "matchup_verified":True,"usable_pregame_identity":True,"goalie_status":"confirmed"}]}
 def test_linked_source_goalie_not_independent_confirmation(self):
  x=reconcile(self.report,self.rosters,self.goalies,{})
  a=x["games"][0]["teams"]["BOS"]
  self.assertEqual(a["source_goalie_player_id"],123)
  self.assertFalse(a["independent_goalie_confirmation"])
  self.assertIsNone(a["expected_lineup"])
  self.assertIn("goalie_not_independently_confirmed",a["blockers"])
 def test_cross_fixture_goalie_rejected(self):
  self.goalies["observations"][0]["game_id"]="2"
  x=reconcile(self.report,self.rosters,self.goalies,{})
  self.assertIsNone(x["games"][0]["teams"]["BOS"]["source_goalie_player_id"])
 def test_late_roster_rejected(self):
  self.rosters["rosters"][0]["as_of"]="2026-10-30T20:00:00Z"
  with self.assertRaises(ValueError):reconcile(self.report,self.rosters,self.goalies,{})
 def test_editorial_unattested_does_not_create_lineup(self):
  editorial={"fixture_attested":True,"observation":{"fixture_mapping_verified":True,
    "publication_date_verified":True,"player_ids_resolved":False}}
  x=reconcile(self.report,self.rosters,self.goalies,editorial)
  self.assertIsNone(x["games"][0]["teams"]["BOS"]["expected_lineup"])
 def test_name_normalization(self):
  self.assertEqual(normalize("  José   Núñez "),"jose nunez")
if __name__=="__main__":unittest.main()
