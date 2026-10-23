import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_depth_snapshots import select_pregame_depth
class TestDepth(unittest.TestCase):
    def test_last_snapshot_strictly_before_kickoff(self):
        g=pd.DataFrame([{"game_id":"g","season":2025,"gameday":"2025-09-07","gametime":"13:00","home_team":"H","away_team":"A"}])
        d=pd.DataFrame([
           {"dt":"2025-09-06T12:00:00Z","team":"H","gsis_id":"old","pos_abb":"CB","pos_slot":1,"pos_rank":1},
           {"dt":"2025-09-07T16:00:00Z","team":"H","gsis_id":"current","pos_abb":"CB","pos_slot":1,"pos_rank":1},
           {"dt":"2025-09-07T18:00:00Z","team":"H","gsis_id":"future","pos_abb":"CB","pos_slot":1,"pos_rank":1}])
        x=select_pregame_depth(g,d)
        self.assertEqual(x.gsis_id.tolist(),["current"])
    def test_unknown_not_healthy(self):
        g=pd.DataFrame([{"game_id":"g","season":2025,"gameday":"2025-09-07","gametime":"13:00","home_team":"H","away_team":"A"}])
        d=pd.DataFrame([{"dt":"2025-09-07T20:00:00Z","team":"H","gsis_id":"late","pos_abb":"CB","pos_slot":1,"pos_rank":1}])
        self.assertEqual(len(select_pregame_depth(g,d)),0)
if __name__=="__main__":unittest.main()
