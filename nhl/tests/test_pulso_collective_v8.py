import unittest
from datetime import datetime,timedelta,timezone
from nhl.pulso_collective_v8 import publish
class TestCollective(unittest.TestCase):
 def sample(self):
  start=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
  asof=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
  fixture={"game_id":"999","home":"EDM","away":"COL","start_utc":start}
  players=[{"player_id":str(i+10000),"team":team,"status":"confirmed"} for team in ("EDM","COL") for i in range(12)]
  snapshot={"game_id":"999","home_team":"EDM","away_team":"COL","asof_utc":asof,"source_url":"https://example.org/roster","players":players}
  goalies=[{"game_id":"999","team":t,"status":"confirmed","confirmation_evidence_url":"https://example.org/confirmation","source_url":"https://example.org/goalie","asof_utc":asof} for t in ("EDM","COL")]
  evidence={"asof_utc":asof,"source_url":"https://example.org/scoring","rates":{"home":3.1,"away":2.9}}
  for k in ("crs","units","goalie","special_teams","context","rivalry"):evidence[k]={"verified":True}
  return fixture,snapshot,goalies,evidence
 def test_missing_goalie_never_predicts(self):
  f,s,g,e=self.sample()
  r=publish(f,s,g[:1],e)
  self.assertEqual(r["status"],"unavailable")
  self.assertIsNone(r["probabilities"])
 def test_incomplete_lineup_never_predicts(self):
  f,s,g,e=self.sample();s["players"]=s["players"][:5]
  r=publish(f,s,g,e);self.assertEqual(r["status"],"unavailable")
 def test_unverified_module_blocks(self):
  f,s,g,e=self.sample();e["special_teams"]={"verified":False}
  self.assertIn("missing_verified_special_teams",publish(f,s,g,e)["readiness_issues"])
 def test_simulation_is_explicitly_experimental(self):
  f,s,g,e=self.sample();r=publish(f,s,g,e)
  self.assertEqual(r["status"],"research_only_not_calibrated")
  self.assertFalse(r["official"]);self.assertFalse(r["bet_authorized"])
  self.assertAlmostEqual(sum(r["probabilities"]["regulation"].values()),1.,places=3)
  self.assertAlmostEqual(sum(r["probabilities"]["illustrative_ml"].values()),1.,places=3)
 def test_late_snapshot_is_rejected(self):
  f,s,g,e=self.sample();s["asof_utc"]=f["start_utc"]
  self.assertEqual(publish(f,s,g,e)["status"],"unavailable")
if __name__=="__main__":unittest.main()
