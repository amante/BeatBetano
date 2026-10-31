import unittest
from nhl.pulso_source_coverage_249 import audit,BLOCKS

class Coverage249(unittest.TestCase):
 def setUp(self):
  at="2026-10-30T16:00:00Z"
  game={"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-10-30T23:00:00Z"}
  self.report={"data_kind":"source_readiness_only","official_predictions":0,"generated_at_utc":at,"games":[game]}
  self.identity={"kind":"nhl_fixture_identity_gate_248","as_of_utc":at,"games":[{
   **game,"teams":{team:{"roster_candidate_count":20,"source_goalie_player_id":100,
    "source_goalie_status":"unverified","independent_goalie_confirmation":False,
    "editorial_lineup_identity_verified":False,"expected_lineup":None,
    "blockers":["goalie_not_independently_confirmed"]} for team in ("BOS","MTL")}}]}
  self.individual={"kind":"nhl_individual_player_goalie_evidence_247","as_of_utc":at,"games":[{
   **game,"teams":{team:{"status":"blocked","blockers":["missing_verified_game_lineups_and_player_history"],
    "availability_delta":None} for team in ("BOS","MTL")}}]}
  self.form={"kind":"nhl_live_sporting_observations_246","observed_at_utc":at,"games":[{
   **game,"sides":{team:{"status":"observed_not_calibrated","blocked":[],
    "features":{"source_url":"https://api-web.nhle.com/v1/standings/2026-10-29"}}
    for team in ("BOS","MTL")}}]}
 def run_audit(self):
  return audit(self.report,self.identity,self.individual,self.form)
 def test_real_evidence_vs_unconfirmed(self):
  x=self.run_audit()
  self.assertEqual(set(x["coverage"]),set(BLOCKS))
  self.assertEqual(x["coverage"]["roster_candidates"]["observed"],2)
  self.assertEqual(x["coverage"]["goalie_identity"]["observed"],2)
  self.assertEqual(x["coverage"]["goalie_confirmed"]["observed"],0)
  self.assertEqual(x["coverage"]["lineup"]["observed"],0)
  self.assertEqual(x["coverage"]["team_form"]["observed"],2)
  self.assertEqual(x["official_predictions"],0)
 def test_cross_fixture_rejected(self):
  self.identity["games"][0]["away"]="TOR"
  with self.assertRaises(ValueError):self.run_audit()
 def test_future_data_rejected(self):
  self.form["observed_at_utc"]="2026-10-30T17:00:00Z"
  with self.assertRaises(ValueError):self.run_audit()
 def test_missing_fixture_rejected(self):
  self.individual["games"]=[]
  with self.assertRaises(ValueError):self.run_audit()
 def test_empty_schedule(self):
  self.report["games"]=[]
  for x in (self.identity,self.individual,self.form):x["games"]=[]
  result=self.run_audit()
  self.assertEqual(result["team_sides"],0)
  self.assertIsNone(result["coverage"]["lineup"]["percentage"])
if __name__=="__main__":unittest.main()
