import unittest
from multisport.sport_adapters import adapt
class AdapterTests(unittest.TestCase):
 def test_nhl_provisional_never_promoted(self):
  x={"as_of_utc":"2026-10-27T18:00:00Z","games":[{"event_id":"1","start_utc":"2026-10-27T23:00:00Z","home":"BOS","away":"MTL","illustrative_ml":{"home":.7}}]}
  out=adapt("nhl",x)
  self.assertEqual(out["events"][0]["final_probability"],None)
  self.assertTrue(out["events"][0]["source_candidate_available"])
  self.assertFalse(out["automatic_promotion"])
 def test_nfl(self):
  x={"as_of_utc":"2026-10-27T18:00:00Z","events":[{"event_id":"1","start_utc":"2026-10-27T23:00:00Z","home_team":"A","away_team":"B"}]}
  self.assertEqual(len(adapt("nfl",x)["events"]),1)
 def test_nba(self):
  x={"created_at_utc":"2026-10-27T18:00:00Z","predictions":[{"game_id":"1","tipoff_utc":"2026-10-27T23:00:00Z","home_team":"A","away_team":"B"}]}
  self.assertEqual(len(adapt("nba",x)["events"]),1)
 def test_reject_started(self):
  x={"as_of_utc":"2026-10-27T23:00:00Z","games":[{"event_id":"1","start_utc":"2026-10-27T23:00:00Z","home":"BOS","away":"MTL"}]}
  with self.assertRaises(ValueError):adapt("nhl",x)
if __name__=="__main__":unittest.main()
