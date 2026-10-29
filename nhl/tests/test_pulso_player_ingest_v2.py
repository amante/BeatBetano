import unittest
from nhl.pulso_player_ingest_v2 import normalize_player,to_minutes,collect
def record(game,day,shots=3):
 return {"gameId":game,"gameDate":day,"teamAbbrev":"EDM","opponentAbbrev":"LAK",
 "homeRoadFlag":"R","toi":"21:30","shots":shots,"goals":1}
class NHLIngestionTests(unittest.TestCase):
 def test_time(self):self.assertAlmostEqual(to_minutes("21:30"),21.5)
 def test_prior_game_rest_and_validation(self):
  raw=[record(1,"2026-10-01"),record(2,"2026-10-03")]
  rows=normalize_player("8478402",raw)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["rest_days"],1)
  self.assertEqual(rows[0]["shots_on_goal"],3)
 def test_source_contract_and_multiple_seasons(self):
  def fake(url):
   if "20232024" in url:return {"gameLog":[record(1,"2023-10-01"),record(2,"2023-10-04")]}
   return {"gameLog":[record(3,"2024-10-01")]}
  rows,sources=collect(["8478402"],("20232024","20242025"),fake)
  self.assertEqual(len(rows),2)
  self.assertEqual(len(sources),2)
 def test_fail_closed_on_missing_source(self):
  with self.assertRaises(ValueError):collect(["8478402"],("20252026",),lambda url:{"error":"missing"})
if __name__=="__main__":unittest.main()
