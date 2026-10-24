import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_feed import parse_current
class Tests(unittest.TestCase):
    def example(self):
        def e(i,date,state,completed=False):
            return {"id":str(i),"date":date,"season":{"type":2,"year":2027},
             "competitions":[{"status":{"type":{"state":state,"completed":completed}},
              "competitors":[{"homeAway":"home","team":{"abbreviation":"BOS"},"score":"110"},
                             {"homeAway":"away","team":{"abbreviation":"NYK"},"score":"99"}]}]}
        return {"events":[e(1,"2026-10-24T00:00:00Z","pre"),
                          e(2,"2026-10-22T00:00:00Z","post",True),
                          e(3,"2026-10-23T18:00:00Z","in")]}
    def test_current_feed_separates_future_from_final(self):
        a=parse_current(self.example(),"2026-10-23T21:00:00Z")
        self.assertEqual([g["game_id"] for g in a["future_fixtures"]],["1"])
        self.assertEqual([g["game_id"] for g in a["completed_games"]],["2"])
        self.assertIsNone(a["future_fixtures"][0]["home_points"])
    def test_post_tipoff_game_never_future(self):
        a=parse_current(self.example(),"2026-10-24T00:01:00Z")
        self.assertEqual(a["future_fixtures"],[])
    def test_no_naive_timestamp(self):
        with self.assertRaises(ValueError):parse_current(self.example(),"2026-10-23T21:00:00")
if __name__=="__main__":unittest.main()
