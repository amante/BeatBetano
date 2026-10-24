import sys,unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import auto_history

class Tests(unittest.TestCase):
    def test_no_future_results_in_current_season(self):
        dates=[]
        def fake_ingest(path,start,end):
            dates.append((start,end))
            year={2023:2024,2024:2025,2025:2026,2026:2027}[int(start[:4])]
            return [{"game_id":f"{year}-{i}","season":year,
                     "tipoff_utc":f"{int(start[:4])}-10-01T00:00:00Z",
                     "home_team":"BOS","away_team":"NYK",
                     "home_points":101,"away_points":99} for i in range(1230 if year!=2027 else 1)]
        with TemporaryDirectory() as d:
            with patch.object(auto_history,"ingest",side_effect=fake_ingest):
                with patch.object(auto_history,"clean",side_effect=lambda x:(x,{"coverage_verified":True})):
                    report=auto_history.build(Path(d)/"history.json","2026-10-24",
                         "2026-10-23T22:00:00Z",Path(d)/"raw")
        self.assertEqual(dates[-1][1],"2026-10-22")
        self.assertEqual(report["current_prior_games"],1)
    def test_reject_naive_timestamp(self):
        with TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"UTC"):
                auto_history.build(Path(d)/"x","2026-10-24","2026-10-23T22:00:00",d)
if __name__=="__main__":unittest.main()
