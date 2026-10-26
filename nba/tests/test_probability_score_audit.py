import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probability_score_audit import audit
def fixture():
 s={"content_sha256":"abc","predictions":[{"game_id":"1","home_team":"MIL","away_team":"IND",
 "elo_p_home":.611,"challenger_p_home":.547,"hybrid_p_home":.547,"hybrid_route":"challenger"}]}
 p={"snapshot_sha256":"abc","games":{"1":{"projections":{
 "MIL":{"projected_points":116.3},"IND":{"projected_points":121.5}}}}}
 return s,p
class Tests(unittest.TestCase):
 def test_ind_mil_disagreement(self):
  r=audit(*fixture())
  self.assertEqual(r["games"][0]["projected_home_margin"],-5.2)
  self.assertTrue(r["games"][0]["requires_manual_review"])
  self.assertEqual(r["hybrid_disagreements"],1)
  self.assertFalse(r["sporting_adjustment_applied"])
 def test_missing_points_not_conflict(self):
  a,b=fixture();b["games"]["1"]["projections"]["MIL"]["projected_points"]=None
  self.assertFalse(audit(a,b)["games"][0]["requires_manual_review"])
 def test_hash_mismatch(self):
  a,b=fixture();b["snapshot_sha256"]="wrong"
  with self.assertRaises(ValueError):audit(a,b)
if __name__=="__main__":unittest.main()
