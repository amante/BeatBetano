import unittest
from multisport.historical_protocol import audit
class HistoricalProtocolTests(unittest.TestCase):
 def test_five_sports(self):
  for sport in ("nba","nfl","nhl","soccer","tennis"):
   with self.subTest(sport=sport):
    r,m=audit([{"id":"a","date":"2026-10-26","home":"H","away":"A","hg":2,"ag":1}],sport,1,"artifact:123")
    self.assertEqual(len(r),1)
    self.assertTrue(m["coverage_complete"])
    self.assertFalse(m["point_in_time_pregame_features_verified"])
    self.assertFalse(m["official_model_promoted"])
 def test_duplicate_and_missing_fail(self):
  row={"id":"1","date":"2026-01-01","home":"H","away":"A","hg":1,"ag":0}
  with self.assertRaisesRegex(ValueError,"Duplicate"):audit([row,row],"nba",2,"test")
  with self.assertRaisesRegex(ValueError,"Coverage"):audit([row],"nba",2,"test")
  with self.assertRaisesRegex(ValueError,"source"):audit([row],"nba",1,"")
 def test_deterministic_hash(self):
  a={"id":"1","date":"2026-01-01","home":"A","away":"B","hg":2,"ag":1}
  b={"id":"2","date":"2026-01-02","home":"C","away":"D","hg":0,"ag":3}
  self.assertEqual(audit([a,b],"nhl",2,"x")[1]["sha256"],audit([b,a],"nhl",2,"x")[1]["sha256"])
if __name__=="__main__":unittest.main()
