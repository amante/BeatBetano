import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_availability_walkforward import walkforward
from nfl_epa import FEATURES

class TestWalkforward(unittest.TestCase):
    def fixture(self):
        rows=[]
        for year in [2021,2022,2023,2024,2025]:
            for i in range(110):
                row={"season":year,"game_id":f"{year}-{i}","home_win":i%2}
                row.update({c:(i%7)/10 for c in FEATURES})
                row.update({f"{side}out_{pos}":int(i%5==0) for side in ["home_","away_"] for pos in ["qb","ol","edge","dt","lb","cb","s"]})
                rows.append(row)
        return pd.DataFrame(rows)
    def test_only_later_years_evaluated(self):
        df=self.fixture()
        preds,report=walkforward(df,min_train=200,min_test=100)
        self.assertEqual(report["holdout_seasons"],[2023,2024,2025])
        self.assertEqual(len(preds),330)
    def test_missing_availability_rejected(self):
        df=self.fixture().drop(columns=["home_out_cb"])
        with self.assertRaisesRegex(ValueError,"Require seven injury"):
            walkforward(df)
    def test_duplicate_games_rejected(self):
        df=self.fixture()
        with self.assertRaisesRegex(ValueError,"Duplicate game"):
            walkforward(pd.concat([df,df.iloc[:1]],ignore_index=True))
if __name__=="__main__":unittest.main()
