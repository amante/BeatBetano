import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nba_official_pace_capture import parse,collect
FIELDS=["TEAM_ID","TEAM_NAME","GP","PACE","POSS","OFF_RATING","DEF_RATING","OREB_PCT","TM_TOV_PCT"]
class Resp:
 def raise_for_status(self):pass
 def json(self):return {"resultSets":[{"headers":FIELDS,"rowSet":[[1,"Team",3,99.4,298.2,112.1,109.2,28.1,13.4]]}]}
class Session:
 def get(self,url,params,headers,timeout):
  self.params=params;return Resp()
class Tests(unittest.TestCase):
 def test_official_advanced_and_prior_date(self):
  session=Session();out=collect("2026-10-27",session,"2026-10-27T02:00:00Z")
  self.assertEqual(out["status"],"observed_unvalidated")
  self.assertEqual(session.params["DateTo"],"10/26/2026")
  self.assertEqual(out["teams"][0]["PACE"],99.4)
 def test_earlier_capture_excludes_current_day(self):
  s=Session();collect("2026-10-27",s,"2026-10-26T21:00:00Z")
  self.assertEqual(s.params["DateTo"],"10/25/2026")
 def test_incompatible_schema_fails(self):
  with self.assertRaises(ValueError):parse({"resultSets":[{"headers":["TEAM_ID"],"rowSet":[[1]]}]})
if __name__=="__main__":unittest.main()
