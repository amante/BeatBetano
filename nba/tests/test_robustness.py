import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from robustness import metric,report
class TestRobustness(unittest.TestCase):
    def test_elo_equal_challenger(self):
        r=metric([{"y":1,"elo":0.7,"challenger":0.7}])
        self.assertAlmostEqual(r["brier_elo"],r["brier_challenger"])
    def test_empty_segment(self):
        self.assertEqual(metric([])["n"],0)
    def test_reject_incomplete(self):
        with self.assertRaisesRegex(ValueError,"three validated"):
            report([])
if __name__=="__main__":unittest.main()
