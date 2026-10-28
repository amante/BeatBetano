import unittest
from nhl.quantitative_roster_delta import compare
class QuantitativeRosterDeltaTests(unittest.TestCase):
 def setUp(self):
  self.history={"team":"BOS","date":"2026-10-27","players":{
    "101":{"role":"skater","observed":10,"goals":5,"shots":30},
    "102":{"role":"skater","observed":10,"goals":2,"shots":20},
    "103":{"role":"skater","observed":10,"goals":4,"shots":20}}}
  self.base={"team":"BOS","source":"dated historical reference","as_of":"2026-10-27T19:00:00Z",
   "players":[{"player_id":101,"unit":"top6","status":"projected","expected_share":1.},
              {"player_id":102,"unit":"top6","status":"projected","expected_share":1.}]}
  self.expected={"team":"BOS","source":"verified daily lines","as_of":"2026-10-28T10:00:00Z",
   "players":[{"player_id":103,"unit":"top6","status":"projected","expected_share":1.},
              {"player_id":102,"unit":"top6","status":"projected","expected_share":1.}]}
 def test_exact_roster_delta(self):
  result=compare(self.history,self.base,self.expected,"2026-10-28T12:00:00Z")
  self.assertEqual(result["baseline_skater_offense_proxy"],.95)
  self.assertEqual(result["crs_skater_offense_proxy"],.8)
  self.assertEqual(result["availability_delta_skater_offense_proxy"],-.15)
  self.assertEqual(result["outgoing_ids"],[101])
  self.assertEqual(result["incoming_ids"],[103])
  self.assertIsNone(result["full_crs_numeric_rating"])
 def test_missing_data_fails_closed(self):
  self.expected["players"][0]["player_id"]=404
  result=compare(self.history,self.base,self.expected,"2026-10-28T12:00:00Z")
  self.assertIsNone(result["crs_skater_offense_proxy"])
  self.assertIsNone(result["availability_delta_skater_offense_proxy"])
  self.assertEqual(result["expected"]["missing"],[404])
 def test_future_lineup_rejected(self):
  self.expected["as_of"]="2026-10-28T13:00:00Z"
  with self.assertRaisesRegex(ValueError,"Future"):
   compare(self.history,self.base,self.expected,"2026-10-28T12:00:00Z")
 def test_low_history_fails_closed(self):
  self.history["players"]["103"]["observed"]=1
  self.assertIsNone(compare(self.history,self.base,self.expected,"2026-10-28T12:00:00Z")["availability_delta_skater_offense_proxy"])
if __name__=="__main__":unittest.main()
