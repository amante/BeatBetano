import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from espn_games import parse_events
class Tests(unittest.TestCase):
    def test_completed_regular_game(self):
        e={"id":"123","date":"2024-10-24T23:00:00Z","season":{"year":2025,"type":2},
           "competitions":[{"status":{"type":{"completed":True}},
             "competitors":[{"homeAway":"home","score":"110","team":{"abbreviation":"BOS"}},
                            {"homeAway":"away","score":"106","team":{"abbreviation":"NYK"}}]}]}
        x=parse_events({"events":[e]})
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]["home_team"],"BOS")
    def test_nonfinal_rejected(self):
        e={"id":"123","date":"2024-10-24T23:00:00Z","season":{"year":2025,"type":2},
           "competitions":[{"status":{"type":{"completed":False}},
             "competitors":[{"homeAway":"home","score":"50","team":{"abbreviation":"BOS"}},
                            {"homeAway":"away","score":"40","team":{"abbreviation":"NYK"}}]}]}
        self.assertEqual(parse_events({"events":[e]}),[])
if __name__=="__main__":unittest.main()
