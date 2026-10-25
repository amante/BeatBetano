import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from early_season import shrinkage
class Tests(unittest.TestCase):
    def test_no_history_defaults_elo(self):
        self.assertAlmostEqual(shrinkage(.6,.8,0,5)["candidate_p_home"],.6)
    def test_half_coverage_blends(self):
        a=shrinkage(.6,.8,5,8)
        self.assertAlmostEqual(a["candidate_p_home"],.7)
        self.assertFalse(a["production_approved"])
    def test_full_coverage_uses_challenger(self):
        self.assertAlmostEqual(shrinkage(.6,.8,10,11)["candidate_p_home"],.8)
if __name__=="__main__":unittest.main()
