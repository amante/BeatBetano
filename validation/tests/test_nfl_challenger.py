import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_challenger import build_features

class ChallengerTests(unittest.TestCase):
    def test_same_day_outcomes_are_not_used(self):
        base=[
            dict(season=2023,gameday="2023-09-01",home_team="A",away_team="B",home_score=40,away_score=10),
            dict(season=2023,gameday="2023-09-01",home_team="A",away_team="C",home_score=10,away_score=40),
            dict(season=2023,gameday="2023-09-08",home_team="B",away_team="A",home_score=30,away_score=13)]
        d=build_features(pd.DataFrame(base))
        self.assertEqual(d.iloc[0].form_net_diff,d.iloc[1].form_net_diff)
        changed=[dict(r) for r in base]
        changed[0]["home_score"]=99
        alt=build_features(pd.DataFrame(changed))
        self.assertEqual(d.iloc[1].form_net_diff,alt.iloc[1].form_net_diff)
        self.assertNotEqual(d.iloc[2].form_net_diff,alt.iloc[2].form_net_diff)

if __name__=="__main__":unittest.main()
