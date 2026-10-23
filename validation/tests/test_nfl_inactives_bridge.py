import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_inactives_bridge import link_inactives

class InactiveBridgeTests(unittest.TestCase):
    def depth(self):
        return pd.DataFrame([{"game_id":"g","team":"H","gsis_id":p,"dt":"2025-09-06T12:00:00Z",
            "kickoff_utc":"2025-09-07T17:00:00Z","pos_abb":"CB","pos_slot":i,
            "pos_rank":i} for i,p in enumerate(["P1","P2"],1)])
    def snapshot(self,time="2025-09-07T15:00:00Z"):
        return pd.DataFrame([{"game_id":"g","team":"H","gsis_id":"P1","inactive":True,
            "observed_at_utc":time,"kickoff_utc":"2025-09-07T17:00:00Z","source":"fixture"}])
    def test_missing_player_remains_unknown(self):
        out=link_inactives(self.depth(),self.snapshot())
        self.assertTrue(bool(out.iloc[0].confirmed_inactive))
        self.assertFalse(bool(out.iloc[1].inactive_known))
        self.assertTrue(pd.isna(out.iloc[1].confirmed_inactive))
    def test_postkickoff_status_rejected(self):
        with self.assertRaisesRegex(ValueError,"precede kickoff"):
            link_inactives(self.depth(),self.snapshot("2025-09-07T18:00:00Z"))
    def test_postkickoff_depth_rejected(self):
        depth=self.depth()
        depth.loc[0,"dt"]="2025-09-07T18:00:00Z"
        with self.assertRaisesRegex(ValueError,"Depth snapshot"):
            link_inactives(depth,self.snapshot())

if __name__=="__main__": unittest.main()
