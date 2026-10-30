import unittest
from nhl.pulso_official_outcome_audit_219 import label_from_pbp
def sample():
 return {"id":2026020207,"gameState":"OFF","homeTeam":{"abbrev":"STL","score":3},
  "awayTeam":{"abbrev":"BOS","score":1},
  "plays":[
   {"typeDescKey":"goal","periodDescriptor":{"number":1},"details":{"homeScore":1,"awayScore":0}},
   {"typeDescKey":"goal","periodDescriptor":{"number":2},"details":{"homeScore":2,"awayScore":0}},
   {"typeDescKey":"goal","periodDescriptor":{"number":3},"details":{"homeScore":2,"awayScore":1}},
   {"typeDescKey":"goal","periodDescriptor":{"number":3},"details":{"homeScore":3,"awayScore":1}}]}
class Official219(unittest.TestCase):
 def test_final_regulation_and_no_plus3(self):
  x=label_from_pbp(sample())
  self.assertEqual(x["ml_winner"],"home")
  self.assertEqual(x["rt_result"],"home")
  self.assertEqual(x["first_to_plus3"],"None")
 def test_first_three_goal_lead(self):
  x=sample();x["homeTeam"]["score"]=4;x["plays"].append({"typeDescKey":"goal","periodDescriptor":{"number":3},"details":{"homeScore":4,"awayScore":1}})
  r=label_from_pbp(x)
  self.assertEqual(r["first_to_plus3"],"home")
  self.assertEqual(r["home_reached_plus3"],"True")
 def test_unfinished_ignored(self):
  x=sample();x["gameState"]="LIVE"
  self.assertIsNone(label_from_pbp(x))
 def test_corrupted_events_rejected(self):
  x=sample();x["plays"][0]["details"]["homeScore"]=3
  with self.assertRaises(ValueError):label_from_pbp(x)
if __name__=="__main__":unittest.main()
