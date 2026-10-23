import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_availability import availability_features, attach_availability

def item(team,player,status,at="2024-09-07T13:00:00Z",position="CB"):
    return {"game_id":"G","team":team,"player_id":player,"position":position,
            "status":status,"snapshot_utc":at,
            "kickoff_utc":"2024-09-08T17:00:00Z","source":"pregame-test"}

class AvailabilityTests(unittest.TestCase):
    def test_verified_pregame_snapshots(self):
        x=pd.DataFrame([item("H","c1","OUT"),item("H","c2","ACTIVE"),
                        item("A","c3","OUT",position="S")])
        features=availability_features(x,{"pregame-test"})
        games=pd.DataFrame([{"game_id":"G","home_team":"H","away_team":"A"}])
        joined=attach_availability(games,features)
        self.assertEqual(joined.iloc[0].home_out_cb,1)
        self.assertEqual(joined.iloc[0].away_out_s,1)
        self.assertEqual(joined.iloc[0].home_out_qb,0)
    def test_later_snapshot_replaces_earlier(self):
        x=pd.DataFrame([item("H","c1","OUT","2024-09-06T12:00:00Z"),
                        item("H","c1","ACTIVE","2024-09-07T12:00:00Z")])
        self.assertEqual(availability_features(x).iloc[0].out_cb,0)
    def test_post_kickoff_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError,"Leakage"):
            availability_features(pd.DataFrame([item("H","c1","OUT","2024-09-09T00:00:00Z")]))
    def test_missing_team_not_healthy(self):
        x=availability_features(pd.DataFrame([item("H","c1","OUT")]))
        games=pd.DataFrame([{"game_id":"G","home_team":"H","away_team":"A"}])
        self.assertEqual(len(attach_availability(games,x)),0)

if __name__=="__main__":
    unittest.main()
