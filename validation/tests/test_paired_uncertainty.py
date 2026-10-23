import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paired_uncertainty import evaluate

class Tests(unittest.TestCase):
    def test_identical_predictions_have_zero_delta(self):
        data=pd.DataFrame({"season":[2023,2023,2024,2024],
            "home_win":[1,0,1,0],"p_epa":[.7,.4,.6,.2],
            "p_epa_plus_injury_counts":[.7,.4,.6,.2]})
        out=evaluate(data,samples=100,seed=1)
        self.assertEqual(out["brier"]["challenger_minus_baseline"],0)
        self.assertEqual(out["log_loss"]["challenger_minus_baseline"],0)
        self.assertEqual(out["bootstrap_unit"],"season")
    def test_single_season_flagged(self):
        data=pd.DataFrame({"season":[2024,2024],"home_win":[1,0],
            "p_epa":[.7,.4],"p_epa_plus_injury_counts":[.6,.3]})
        self.assertEqual(evaluate(data,samples=50)["bootstrap_unit"],"game_exploratory")
if __name__=="__main__":unittest.main()
