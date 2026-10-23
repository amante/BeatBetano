import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_player_identity import resolve
class Tests(unittest.TestCase):
    def test_duplicate_names_are_unresolved(self):
        p=pd.DataFrame({"gsis_id":["a","b"],"display_name":["Alex Smith","Alex Smith"],"team":["KC","KC"]})
        e=pd.DataFrame({"player_name":["Alex Smith"],"team":["KC"]})
        out=resolve(e,p)
        self.assertEqual(out.identity_status.iloc[0],"unresolved")
    def test_unique_candidate_not_auto_confirmed(self):
        p=pd.DataFrame({"gsis_id":["a"],"display_name":["Alex Smith"],"team":["KC"]})
        e=pd.DataFrame({"player_name":["Alex Smith"],"team":["KC"]})
        self.assertEqual(resolve(e,p).identity_status.iloc[0],"single_name_candidate_requires_review")
if __name__=="__main__":unittest.main()
