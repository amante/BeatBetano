import unittest
from nhl.pulso_boxscore_schema_audit_266 import audit
class Schema266(unittest.TestCase):
 def fixture(self):
  label={"game_id":"2026020001","date":"2026-10-07","home":"BOS","away":"MTL"}
  box={"id":2026020001,"gameDate":"2026-10-07",
       "playerByGameStats":{"homeTeam":{"goalies":[{"playerId":10,"starter":True}]},
        "awayTeam":{"goalies":[{"playerId":20,"starter":True}]}}}
  return label,box
 def test_two_explicit_starters(self):
  l,b=self.fixture()
  out=audit([l],lambda _: (b,{"url":"official","sha256":"a"*64}))
  self.assertEqual(out["both_starters_explicit"],1)
  self.assertEqual(out["games"][0]["teams"]["home"]["verified_starter_id"],10)
 def test_missing_starter_is_not_inferred(self):
  l,b=self.fixture();b["playerByGameStats"]["homeTeam"]["goalies"][0].pop("starter")
  self.assertEqual(audit([l],lambda _:(b,{}))["both_starters_explicit"],0)
 def test_missing_schema_is_blocked(self):
  l,b=self.fixture();b.pop("playerByGameStats")
  self.assertEqual(audit([l],lambda _:(b,{}))["status_counts"]["blocked_ValueError"],1)
 def test_duplicate_ids_blocked(self):
  l,b=self.fixture();b["playerByGameStats"]["homeTeam"]["goalies"]*=2
  self.assertEqual(audit([l],lambda _:(b,{}))["status_counts"]["blocked_ValueError"],1)
 def test_fixture_mismatch_blocked(self):
  l,b=self.fixture();b["id"]=1
  self.assertEqual(audit([l],lambda _:(b,{}))["status_counts"]["blocked_ValueError"],1)
 def test_sample_limit(self):
  l,b=self.fixture()
  with self.assertRaises(ValueError):audit([l],limit=51)
if __name__=="__main__":unittest.main()
