import unittest
from nhl.roster_source_adapter import adapt,evaluate
class SourceAdapterTests(unittest.TestCase):
 def setUp(self):
  self.time="2026-10-28T18:00:00Z"
  self.source={"team":"BOS","source_url":"https://example.org/dated-lines","as_of":"2026-10-28T12:00:00Z",
    "lineup_type":"projected","players":[{"player_id":101,"unit":"top6","status":"projected","expected_share":1.}]}
 def test_source_adapter(self):
  self.assertEqual(adapt(self.source,"BOS",self.time)["players"][0]["player_id"],101)
 def test_missing_source_rejected(self):
  with self.assertRaisesRegex(ValueError,"Source URL"):
   adapt(dict(self.source,source_url=""),"BOS",self.time)
 def test_future_source_rejected(self):
  with self.assertRaisesRegex(ValueError,"newer"):
   adapt(dict(self.source,as_of="2026-10-29T12:00:00Z"),"BOS",self.time)
 def test_projected_not_confirmed(self):
  x=dict(self.source,players=[dict(self.source["players"][0],status="confirmed")])
  with self.assertRaisesRegex(ValueError,"Projected lineup"):
   adapt(x,"BOS",self.time)
 def test_delta_from_two_sourced_snapshots(self):
  past={"team":"BOS","date":"2026-10-27","players":{"101":{"role":"skater","observed":10,"goals":5,"shots":30},
    "102":{"role":"skater","observed":10,"goals":3,"shots":20}}}
  replacement=dict(self.source,players=[dict(self.source["players"][0],player_id=102)])
  result=evaluate(past,self.source,replacement,self.time)
  self.assertEqual(result["availability_delta_skater_offense_proxy"],-.25)
  self.assertIsNone(result["goalie_rating"])
if __name__=="__main__":unittest.main()
