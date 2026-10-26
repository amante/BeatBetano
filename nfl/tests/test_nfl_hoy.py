import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_hoy import fixtures,report

def event(eid,start,state="pre",completed=False):
    return {"id":eid,"date":start,"season":{"type":2},
     "competitions":[{"competitors":[
       {"homeAway":"home","team":{"abbreviation":"KC"}},
       {"homeAway":"away","team":{"abbreviation":"SEA"}}],
       "status":{"type":{"state":state,"completed":completed}}}]}

class Tests(unittest.TestCase):
    def test_only_future_games(self):
        x={"events":[event("1","2026-10-25T20:00:00Z"),event("2","2026-10-25T10:00:00Z")]}
        rows,counts=fixtures(x,"2026-10-25T12:00:00Z")
        self.assertEqual([g["event_id"] for g in rows],["1"])
        self.assertEqual(counts["started"],1)
    def test_empty_slate_safe(self):
        data=report({"events":[]},[],"2026-10-25T12:00:00Z")
        self.assertEqual(data["events"],[])
    def test_elo_candidate_never_final(self):
        x=report({"events":[event("1","2026-10-25T20:00:00Z")]},[],
                 "2026-10-25T12:00:00Z")["events"][0]
        self.assertIsNone(x["final_probability"])
        self.assertEqual(x["historical_elo_candidate"],0.578497)
    def test_reject_duplicate(self):
        x={"events":[event("1","2026-10-25T20:00:00Z")]*2}
        with self.assertRaises(ValueError):fixtures(x,"2026-10-25T12:00:00Z")
if __name__=="__main__":unittest.main()
