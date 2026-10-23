import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nflcom_evidence import validate

class NFLComEvidenceTests(unittest.TestCase):
    def row(self):
        return {"game_id":"g","team":"H","player_name":"A Player","position":"CB",
                "game_status":"Out","source_url":"https://www.nfl.com/injuries/league/2025/reg6",
                "captured_at_utc":"2025-10-11T16:00:00Z",
                "kickoff_utc":"2025-10-12T17:00:00Z"}
    def test_capture_passes_but_not_confirmed_inactive(self):
        x=validate(pd.DataFrame([self.row()]))
        self.assertTrue(bool(x.iloc[0].listed_out))
        self.assertTrue(pd.isna(x.iloc[0].confirmed_inactive))
    def test_retroactive_capture_rejected(self):
        d=self.row();d["captured_at_utc"]="2025-10-13T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"pre-kickoff"):
            validate(pd.DataFrame([d]))
    def test_untrusted_domain_rejected(self):
        d=self.row();d["source_url"]="https://nfl.com.example.org/fake"
        with self.assertRaisesRegex(ValueError,"nfl.com"):
            validate(pd.DataFrame([d]))
    def test_questionable_not_equated_out(self):
        d=self.row();d["game_status"]="Questionable"
        self.assertFalse(bool(validate(pd.DataFrame([d])).iloc[0].listed_out))
if __name__=="__main__":unittest.main()
