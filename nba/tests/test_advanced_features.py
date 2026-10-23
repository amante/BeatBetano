import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from advanced_features import validate_rows,last_completed_season_features
class Tests(unittest.TestCase):
    def row(self,year,bpm=2.0,team="BOS"):
        return {"player_id":"p1","season_end_year":year,"team":team,"games":70,
                "minutes":2300,"per":18.5,"ts_pct":0.59,"bpm":bpm,
                "vorp":2.4,"ws_per_48":0.17}
    def test_future_seasons_excluded(self):
        data=[self.row(2024,1),self.row(2025,2),self.row(2026,99)]
        result=last_completed_season_features(data,2026)
        self.assertEqual(result[0]["prior_bpm"],2)
        self.assertEqual(result[0]["feature_season_end_year"],2025)
    def test_cross_team_ambiguous_not_assigned(self):
        rows=[self.row(2025,team="BOS"),self.row(2025,team="LAL")]
        self.assertEqual(last_completed_season_features(rows,2026),[])
    def test_reject_duplicate_rows(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            validate_rows([self.row(2024),self.row(2024)])
if __name__=="__main__":unittest.main()
