import unittest
from nhl.pulso_pregame_v7 import audit_snapshot,project_players,audit_dated_predictions
class TestPregame(unittest.TestCase):
 def snapshot(self):
  return {"asof_utc":"2026-10-29T17:00:00Z","source_url":"https://example.org/verified/roster","game_id":"fixture1","home_team":"EDM","away_team":"COL","players":[{"player_id":"97","team":"EDM","status":"confirmed"},{"player_id":"29","team":"COL","status":"probable"},{"player_id":"91","team":"COL","status":"out"}]}
 def test_incomplete_roster_never_claims_full(self):
  a=audit_snapshot(self.snapshot(),"2026-10-29T23:00:00Z")
  self.assertFalse(a["eligible_for_full_team_prediction"])
  self.assertEqual(len(a["usable_players"]),2)
 def test_future_or_same_timestamp_is_rejected(self):
  s=self.snapshot();s["asof_utc"]="2026-10-29T23:00:00Z"
  with self.assertRaises(ValueError):audit_snapshot(s,"2026-10-29T23:00:00Z")
 def test_forecast_missing_player_history_not_fabricated(self):
  r=project_players([],self.snapshot(),"2026-10-29T23:00:00Z",{"EDM":1,"COL":0})
  self.assertEqual(len(r["player_predictions"]),2)
  self.assertTrue(all(p["forecast"]["projection"] is None for p in r["player_predictions"]))
 def test_unknown_rest_fails_closed(self):
  with self.assertRaises(ValueError):project_players([],self.snapshot(),"2026-10-29T23:00:00Z",{"EDM":1})
 def test_audit_rejects_after_puck_drop(self):
  a=audit_dated_predictions([{"game_id":"1","player_id":"97","source_asof_utc":"2026-10-29T23:01:00Z","cutoff_utc":"2026-10-29T23:00:00Z"}])
  self.assertEqual(a["errors"][0]["error"],"source_not_pregame")
if __name__=="__main__":unittest.main()
