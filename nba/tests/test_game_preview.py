import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_preview import extract_game
class Tests(unittest.TestCase):
    def test_summary_never_claims_starters(self):
        r=extract_game({"injuries":[{"injuries":[{"athlete":{"displayName":"Player X"},"status":"Out"}]}]},
        {"game_id":"123"},"2026-10-25T20:00:00Z")
        self.assertIsNone(r["confirmed_starting_lineups"])
        self.assertEqual(r["injury_observations"][0]["player"],"Player X")
    def test_mismatched_game_rejected(self):
        with self.assertRaisesRegex(ValueError,"does not match"):
            extract_game({"header":{"competitions":[{"id":"wrong"}]}},{"game_id":"123"},"2026-10-25T20:00:00Z")
if __name__=="__main__":unittest.main()
