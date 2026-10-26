import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from offense_defense_matchups import evaluate
class Tests(unittest.TestCase):
 def fixtures(self):
  s={"content_sha256":"abc","predictions":[{"game_id":"1","home_team":"MIL","away_team":"IND","hybrid_p_home":.547}]}
  p={"snapshot_sha256":"abc","games":{"1":{"teams":{"MIL":{"offensive_rating":112.35,"defensive_rating":120.01,"sample_games":10},"IND":{"offensive_rating":110.7,"defensive_rating":108.62,"sample_games":10}},
  "projections":{"MIL":{"projected_possessions":105.3,"possessions_projected":105.3,"projected_points":116.3},"IND":{"possessions_projected":105.3,"projected_points":121.5}}}}}
  return s,p
 def test_pairwise_opposing_defenses(self):
  r=evaluate(*self.fixtures())["games"]["1"]
  self.assertEqual(r["matchups"]["MIL"]["opponent_drtg"],108.62)
  self.assertEqual(r["matchups"]["IND"]["opponent_drtg"],120.01)
  self.assertTrue(r["direction_conflict"])
  self.assertFalse(r["matchup_adjustment_authorized"])
 def test_missing_team_evidence_fails_closed(self):
  a,b=self.fixtures();b["games"]["1"]["teams"]["MIL"]["offensive_rating"]=None
  r=evaluate(a,b)["games"]["1"]
  self.assertEqual(r["matchups"]["MIL"]["status"],"insufficient_verified_team_sample")
 def test_mismatched_snapshot(self):
  a,b=self.fixtures();b["snapshot_sha256"]="changed"
  with self.assertRaises(ValueError):evaluate(a,b)
if __name__=="__main__":unittest.main()
