import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from guardrails import guardrail
class Tests(unittest.TestCase):
    def test_high_favorite_stays_elo(self):
        p,why=guardrail(.82,.87,10,10)
        self.assertEqual((p,why),(.82,"strong_favorite"))
    def test_sparse_history_stays_elo(self):
        p,why=guardrail(.6,.7,2,10)
        self.assertEqual((p,why),(.6,"insufficient_recent_sample"))
    def test_ordinary_uses_challenger(self):
        p,why=guardrail(.64,.67,10,10)
        self.assertEqual((p,why),(.67,"challenger"))
    def test_bad_probability_rejected(self):
        with self.assertRaises(ValueError):guardrail(1.1,.6,10,10)
if __name__=="__main__":unittest.main()
