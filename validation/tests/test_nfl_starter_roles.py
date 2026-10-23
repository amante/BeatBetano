import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_starter_roles import validate_roles,derive_role_absences,validate_replacements

def row(player,role="CB1",status="OUT",time="2024-09-08T14:00:00Z"):
    return {"game_id":"g","team":"H","player_id":player,"role":role,"status":status,
            "snapshot_utc":time,"kickoff_utc":"2024-09-08T17:00:00Z","source":"verified-fixture"}

class TestStarterRoles(unittest.TestCase):
    def test_cb1_and_nickel_separate(self):
        d=derive_role_absences(pd.DataFrame([row("p1","CB1"),row("p2","NICKEL","ACTIVE")]))
        self.assertTrue(d[d.role=="CB1"].confirmed_absent.iloc[0])
        self.assertFalse(d[d.role=="NICKEL"].confirmed_absent.iloc[0])
    def test_postkickoff_rejected(self):
        with self.assertRaisesRegex(ValueError,"Post-kickoff"):
            validate_roles(pd.DataFrame([row("p1",time="2024-09-08T21:00:00Z")]))
    def test_ambiguous_role_rejected(self):
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            validate_roles(pd.DataFrame([row("p1"),row("p2")]))
    def test_replacement_must_reference_absent_starter(self):
        d=derive_role_absences(pd.DataFrame([row("p1","CB1","ACTIVE")]))
        r=pd.DataFrame([{"game_id":"g","team":"H","absent_player_id":"p1","replacement_player_id":"p2","role":"CB1",
           "snapshot_utc":"2024-09-08T15:00:00Z","kickoff_utc":"2024-09-08T17:00:00Z","source":"fixture"}])
        with self.assertRaisesRegex(ValueError,"confirmed absent"):
            validate_replacements(r,d)
if __name__=="__main__":unittest.main()
