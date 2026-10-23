import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clean_regular import clean
class TestClean(unittest.TestCase):
    def test_insufficient_teams_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"30 franchises"):
            clean([{"game_id":"x","season":2024,"home_team":"BOS","away_team":"NY","tipoff_utc":"2023-12-01T00:00:00Z"}])
    def test_empty(self):
        self.assertEqual(clean([])[1]["coverage_verified"],True)
if __name__=="__main__":unittest.main()
