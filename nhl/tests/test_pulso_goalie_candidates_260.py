import unittest
from copy import deepcopy
from nhl.pulso_goalie_candidates_260 import collect

class CandidateHistory260(unittest.TestCase):
    def setup_data(self):
        at="2026-10-31T14:00:00Z"
        report={"data_kind":"source_readiness_only","generated_at_utc":at,
                "games":[{"game_id":"1","home":"NSH","away":"BUF","start_utc":"2026-10-31T23:00:00Z"}]}
        def c(pid,name):
            return {"player_id":pid,"name":name,"source":"ESPN/NHL roster","status":"candidate"}
        scenarios={"kind":"nhl_goalie_conditional_scenarios_258","as_of_utc":at,
                   "games":[{"game_id":"1","home":"NSH","away":"BUF",
                             "goalie_candidates":{"NSH":[c(10,"A"),c(11,"B")],"BUF":[c(20,"C")]}}]}
        return scenarios,report
    def fetcher(self, pid, season):
        return ({"gameLog":[{"gameDate":"2026-10-29","shotsAgainst":30,
                             "goalsAgainst":3,"gameId":pid}]},
                {"retrieved_at":"2026-10-31T15:00:00Z","url":"fixture","sha256":"e"*64})
    def test_both_alternate_and_first_candidate_are_captured(self):
        s,r=self.setup_data()
        result=collect(s,r,self.fetcher)
        self.assertEqual(result["distinct_candidate_ids"],3)
        self.assertEqual(result["observed_candidates"],3)
        self.assertEqual([a["player_id"] for a in result["games"][0]["teams"]["NSH"]],[10,11])
        self.assertFalse(result["games"][0]["teams"]["NSH"][1]["independently_confirmed_starter"])
    def test_future_record_excluded(self):
        s,r=self.setup_data()
        def fetcher(pid,season):
            return ({"gameLog":[{"gameDate":"2026-10-31","shotsAgainst":30,"goalsAgainst":3}]},
                    {"retrieved_at":"2026-10-31T15:00:00Z"})
        result=collect(s,r,fetcher)
        self.assertEqual(result["observed_candidates"],0)
    def test_post_puckdrop_is_blocked(self):
        s,r=self.setup_data()
        def fetcher(pid,season):
            data,meta=self.fetcher(pid,season)
            meta["retrieved_at"]="2026-10-31T23:01:00Z"
            return data,meta
        result=collect(s,r,fetcher)
        self.assertEqual(result["observed_candidates"],0)
        self.assertEqual(result["games"][0]["teams"]["NSH"][0]["status"],"blocked")
    def test_no_candidate_does_not_fetch(self):
        s,r=self.setup_data()
        s["games"][0]["goalie_candidates"]={"NSH":[],"BUF":[]}
        result=collect(s,r,lambda *_:self.fail("Unexpected network"))
        self.assertEqual(result["distinct_candidate_ids"],0)
    def test_mismatched_fixture_rejected(self):
        s,r=self.setup_data()
        s["games"][0]["away"]="TOR"
        with self.assertRaises(ValueError):collect(s,r,self.fetcher)
    def test_duplicate_candidate_only_fetched_once(self):
        s,r=self.setup_data()
        s["games"][0]["goalie_candidates"]["BUF"].append(deepcopy(s["games"][0]["goalie_candidates"]["NSH"][0]))
        calls=[]
        def fetcher(pid,season):
            calls.append(pid)
            return self.fetcher(pid,season)
        collect(s,r,fetcher)
        self.assertEqual(sorted(calls),[10,11,20])

if __name__=="__main__":
    unittest.main()
