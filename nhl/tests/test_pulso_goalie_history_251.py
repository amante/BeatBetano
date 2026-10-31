import unittest
from nhl.pulso_goalie_history_251 import metrics,season_for,collect
class Goalie251(unittest.TestCase):
 def test_season(self):
  self.assertEqual(season_for("2026-10-31"),"20262027")
  self.assertEqual(season_for("2027-02-01"),"20262027")
 def test_no_same_date_leakage(self):
  x=metrics({"gameLog":[{"gameDate":"2026-10-29","gameId":1,"saves":28,"shotsAgainst":30},
   {"gameDate":"2026-10-31","gameId":2,"saves":30,"shotsAgainst":31}]},"2026-10-31")
  self.assertEqual(x["season_to_date"]["games"],1)
  self.assertEqual(x["season_to_date"]["save_pct"],round(28/30,6))
 def test_real_nhl_goaltender_schema_without_saves(self):
  x=metrics({"gameLog":[{"gameDate":"2026-10-29","gameId":1,
    "shotsAgainst":31,"goalsAgainst":3,"savePctg":0.903226}]},"2026-10-31")
  self.assertEqual(x["season_to_date"]["games"],1)
  self.assertEqual(x["season_to_date"]["saves"],28)
  self.assertEqual(x["season_to_date"]["save_pct"],round(28/31,6))
 def test_goalie_pct_mismatch_rejected(self):
  x=metrics({"gameLog":[{"gameDate":"2026-10-29","gameId":1,
    "shotsAgainst":31,"goalsAgainst":3,"savePctg":0.80}]},"2026-10-31")
  self.assertEqual(x["excluded_bad_records"],1)
 def test_no_guess_when_goals_against_missing(self):
  x=metrics({"gameLog":[{"gameDate":"2026-10-29","gameId":1,
    "shotsAgainst":31,"savePctg":0.9}]},"2026-10-31")
  self.assertEqual(x["season_to_date"]["games"],0)
 def test_bad_shots_not_used(self):
  x=metrics({"gameLog":[{"gameDate":"2026-10-29","saves":31,"shotsAgainst":30}]},"2026-10-31")
  self.assertIsNone(x["season_to_date"]["save_pct"])
  self.assertEqual(x["excluded_bad_records"],1)
 def test_unknown_game_log_is_not_accepted(self):
  with self.assertRaises(ValueError):metrics({},"2026-10-31")
 def test_missing_candidate_does_not_call_http(self):
  report={"generated_at_utc":"2026-10-31T14:00:00Z","data_kind":"source_readiness_only",
   "games":[{"game_id":"1","home":"BOS","away":"MTL","start_utc":"2026-11-01T00:00:00Z"}]}
  identity={"kind":"nhl_fixture_identity_gate_248","as_of_utc":report["generated_at_utc"],
    "games":[{"game_id":"1","home":"BOS","away":"MTL","teams":{
     x:{"source_goalie_player_id":None,"source_goalie_status":"unverified"} for x in ("BOS","MTL")}}]}
  x=collect(report,identity,fetcher=lambda *_:self.fail("unexpected network"))
  self.assertEqual(x["observed_team_sides"],0)
  self.assertEqual(x["candidate_player_ids"],0)
if __name__=="__main__":unittest.main()
