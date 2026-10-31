import unittest
from nhl.pulso_goalie_integration_254 import join
class GoalieJoin254(unittest.TestCase):
 def setUp(self):
  self.report={"generated_at_utc":"2026-10-31T15:00:00Z","games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-11-01T00:00:00Z"}]}
  self.identity={"kind":"nhl_fixture_identity_gate_248","as_of_utc":self.report["generated_at_utc"],"games":[{"game_id":"1","home":"BOS","away":"MTL","teams":{"BOS":{"source_goalie_player_id":123},"MTL":{"source_goalie_player_id":456}}}]}
  self.goalie={"kind":"nhl_goalie_descriptive_daily_253","as_of_utc":self.report["generated_at_utc"],"official_predictions":0,"calibrated":False,"games":[{"game_id":"1","home":"BOS","away":"MTL","teams":{
   "BOS":{"nhl_player_id":123,"starter_status":"not_independently_confirmed","status":"descriptive_evidence_only","season_sv_pct":.92,"shrunk_sv_pct":.91,"recent_5_sv_pct":.93,"season_shots_against":300,"days_since_last_appearance":2},
   "MTL":{"nhl_player_id":456,"starter_status":"not_independently_confirmed","status":"blocked"}}}]}
 def test_metrics_are_visible_without_promoting_starter(self):
  x=join(self.report,self.identity,self.goalie)
  self.assertTrue(x["1"]["BOS"]["observed"])
  self.assertFalse(x["1"]["BOS"]["starter_verified"])
  self.assertIsNone(x["1"]["BOS"]["probability_delta"])
  self.assertFalse(x["1"]["MTL"]["observed"])
 def test_identity_mismatch_rejected(self):
  self.goalie["games"][0]["teams"]["BOS"]["nhl_player_id"]=999
  with self.assertRaises(ValueError):join(self.report,self.identity,self.goalie)
 def test_invalid_save_rate_rejected(self):
  self.goalie["games"][0]["teams"]["BOS"]["shrunk_sv_pct"]=1.5
  with self.assertRaises(ValueError):join(self.report,self.identity,self.goalie)
 def test_starter_promotion_rejected(self):
  self.goalie["games"][0]["teams"]["BOS"]["starter_status"]="confirmed"
  with self.assertRaises(ValueError):join(self.report,self.identity,self.goalie)
 def test_wrong_fixture_rejected(self):
  self.goalie["games"][0]["away"]="TOR"
  with self.assertRaises(ValueError):join(self.report,self.identity,self.goalie)
if __name__=="__main__":unittest.main()
