import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nflcom_game_context import attach_context
class Tests(unittest.TestCase):
    def data(self):
        r=pd.DataFrame([{"source_url":"https://www.nfl.com/injuries/league/2026/REG7",
                        "captured_at_utc":"2026-10-23T16:00:00Z","player_name":"Demo Player",
                        "position":"CB","game_status":"OUT"}])
        a=r[["source_url","player_name","position","game_status"]].copy()
        a["team"]="CHI";a["game_id"]="G"
        g=pd.DataFrame([{"game_id":"G","home_team":"CHI","away_team":"GB",
                         "kickoff_utc":"2026-10-25T17:00:00Z"}])
        return r,a,g
    def test_proven_pregame_mapping(self):
        r,a,g=self.data()
        self.assertEqual(attach_context(r,a,g).context_status.iloc[0],"pregame_context_verified_identity_pending")
    def test_team_mismatch_rejected(self):
        r,a,g=self.data();a["team"]="NYJ"
        self.assertEqual(attach_context(r,a,g).context_status.iloc[0],"invalid_team_game")
    def test_after_kickoff_rejected(self):
        r,a,g=self.data();r["captured_at_utc"]="2026-10-26T12:00:00Z"
        self.assertEqual(attach_context(r,a,g).context_status.iloc[0],"not_pregame")
    def test_unknown_remains_unknown(self):
        r,a,g=self.data()
        self.assertEqual(attach_context(r,a.iloc[:0],g).context_status.iloc[0],"unresolved")
if __name__=="__main__":unittest.main()
