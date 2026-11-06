import sys,unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import auto_history

class Tests(unittest.TestCase):
    def test_no_future_results_in_current_season(self):
        dates=[]
        def fake_delta(path,start,end):
            dates.append((start,end))
            return [{"game_id":"current","season":2027,
                     "tipoff_utc":"2026-10-21T00:00:00Z",
                     "home_team":"BOS","away_team":"NYK",
                     "home_points":101,"away_points":99}], {"network_requests":1}
        with TemporaryDirectory() as d:
            with patch.object(auto_history,"daily_delta",side_effect=fake_delta):
                report=auto_history.build(Path(d)/"history.json","2026-10-24",
                     "2026-10-23T22:00:00Z",Path(d)/"raw")
        self.assertEqual(dates[-1][1],"2026-10-22")
        self.assertEqual(report["current_prior_games"],1)
    def test_reject_naive_timestamp(self):
        with TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"UTC"):
                auto_history.build(Path(d)/"x","2026-10-24","2026-10-23T22:00:00",d)
if __name__=="__main__":unittest.main()
