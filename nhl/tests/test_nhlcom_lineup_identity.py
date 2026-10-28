import unittest
from nhl.nhlcom_lineup_identity import resolve
class LineupIdentityTests(unittest.TestCase):
 def setUp(self):
  self.capture={"retrieved_at":"2026-10-28T12:00:00Z","source_url":"https://www.nhl.com/news/nhl-lineup-projections-2026-27-season",
   "blocks":[{"reported_team_name":"Boston Bruins","lines":["John Smith -- Alex Jones -- Bill White"],"scratched":[],"injured":[]},
             {"reported_team_name":"Montreal Canadiens","lines":["Pierre Martin -- Luc Roy -- Marc Dubois"],"scratched":[],"injured":[]}]}
  self.rosters=[
   {"team":"BOS","as_of":"2026-10-28T11:00:00Z","players":[
     {"player_id":1,"full_name":"John Smith","position_group":"forward"},
     {"player_id":2,"full_name":"Alex Jones","position_group":"forward"},
     {"player_id":3,"full_name":"Bill White","position_group":"forward"}]},
   {"team":"MTL","as_of":"2026-10-28T11:00:00Z","players":[
     {"player_id":4,"full_name":"Pierre Martin","position_group":"forward"},
     {"player_id":5,"full_name":"Luc Roy","position_group":"forward"},
     {"player_id":6,"full_name":"Marc Dubois","position_group":"forward"}]}]
  self.fixture={"game_id":"test","scheduled_start":"2026-10-28T23:00:00Z","publication_date_verified":True,
   "fixture_mapping_verified":True,"teams":[{"code":"BOS","reported_team_name":"Boston Bruins"},{"code":"MTL","reported_team_name":"Montreal Canadiens"}]}
 def test_exact_matching_never_confirms_goalie(self):
  x=resolve(self.capture,self.rosters,self.fixture)
  self.assertEqual(len(x["teams"][0]["projected_skaters"]),3)
  self.assertFalse(x["prediction_eligible"])
  self.assertFalse(x["teams"][0]["starting_goalie_confirmed"])
 def test_ambiguous_name_rejected(self):
  self.rosters[0]["players"].append({"player_id":7,"full_name":"John Smith","position_group":"forward"})
  x=resolve(self.capture,self.rosters,self.fixture)
  self.assertIn("John Smith",x["teams"][0]["unresolved_skaters"])
 def test_post_start_capture_rejected(self):
  self.capture["retrieved_at"]="2026-10-29T01:00:00Z"
  with self.assertRaises(ValueError):resolve(self.capture,self.rosters,self.fixture)
 def test_unattested_fixture_rejected(self):
  self.fixture["publication_date_verified"]=False
  with self.assertRaises(ValueError):resolve(self.capture,self.rosters,self.fixture)
if __name__=="__main__":unittest.main()
