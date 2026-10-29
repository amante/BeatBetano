import unittest
from datetime import datetime,timedelta,timezone
from nhl.pulso_team_bridge import aggregate
class TestBridge(unittest.TestCase):
 def data(self):
  start=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
  before=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
  fixture={"game_id":"100","home":"EDM","away":"COL","start_utc":start}
  players=[{"team":team,"player_id":str(i+1000),"availability":"confirmed","asof_utc":before,
      "forecast":{"projection":{"toi_minutes":15.,"shots_on_goal":2.,"goals":.2}}}
    for team in ("EDM","COL") for i in range(12)]
  goalies={"observations":[{"team":t,"nhl_game_id":"100","usable_pregame_identity":True,
       "nhl_player_id":900+i,"source_captured_at":before} for i,t in enumerate(("EDM","COL"))]}
  return fixture,players,goalies
 def test_full_research_features_never_claims_rates(self):
  f,p,g=self.data();r=aggregate(f,p,g)
  self.assertEqual(r["status"],"research_features_only")
  self.assertEqual(r["team_features"]["EDM"]["sog_volume_proxy"],24.)
  self.assertIsNone(r["probabilities"]);self.assertIsNone(r["collective_goal_rates"])
  self.assertFalse(r["goalie_evidence"]["EDM"]["starter_independently_confirmed"])
 def test_incomplete_is_blocked(self):
  f,p,g=self.data();r=aggregate(f,p[:12],g)
  self.assertEqual(r["status"],"blocked_incomplete_evidence")
  self.assertIn("insufficient_player_coverage_COL",r["readiness_issues"])
 def test_after_start_source_not_used(self):
  f,p,g=self.data();p[0]["asof_utc"]=f["start_utc"]
  r=aggregate(f,p,g);self.assertIn("late_player_source_EDM",r["readiness_issues"])
 def test_duplicate_player_is_rejected(self):
  f,p,g=self.data()
  with self.assertRaises(ValueError):aggregate(f,p+[p[0]],g)
 def test_no_goalie_identity_blocked(self):
  f,p,g=self.data();g["observations"]=[]
  self.assertIn("goalie_identity_unresolved_COL",aggregate(f,p,g)["readiness_issues"])
if __name__=="__main__":unittest.main()
