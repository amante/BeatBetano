import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ngs_weekly import clean,previous_week_features
class Tests(unittest.TestCase):
    def test_week_zero_excluded_and_future_not_used(self):
        d=pd.DataFrame({"season":[2024]*4,"week":[0,1,2,3],
                        "player_gsis_id":["X"]*4,"team_abbr":["KC"]*4,
                        "avg_time_to_throw":[9,2.1,2.4,3.0]})
        x=clean(d,"passing")
        self.assertEqual(x.week.tolist(),[1,2,3])
        out=previous_week_features(x,"passing")
        self.assertTrue(pd.isna(out.iloc[0].prior_avg_time_to_throw))
        self.assertAlmostEqual(out.iloc[1].prior_avg_time_to_throw,2.1)
        self.assertAlmostEqual(out.iloc[2].prior_avg_time_to_throw,2.25)
    def test_same_week_value_cannot_affect_its_prior(self):
        d=pd.DataFrame({"season":[2024,2024],"week":[1,2],
                        "player_gsis_id":["X","X"],"team_abbr":["KC","KC"],
                        "avg_time_to_throw":[2.0,100]})
        out=previous_week_features(clean(d,"passing"),"passing")
        self.assertEqual(out.iloc[1].prior_avg_time_to_throw,2.)
    def test_duplicate_player_week_rejected(self):
        d=pd.DataFrame({"season":[2024,2024],"week":[1,1],
                        "player_gsis_id":["X","X"],"team_abbr":["KC","KC"]})
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            clean(d,"receiving")
if __name__=="__main__":unittest.main()
