import tempfile,unittest
from pathlib import Path
from nhl.pulso_historical_boxscores_265 import capture,extract

class Boxscore265(unittest.TestCase):
    def data(self):
        label={"game_id":"2026020001","date":"2026-10-07","home":"BOS","away":"MTL"}
        box={"id":2026020001,"gameDate":"2026-10-07",
             "playerByGameStats":{"homeTeam":{"goalies":[{"playerId":10,"starter":True}]},
                                  "awayTeam":{"goalies":[{"playerId":20,"starter":True}]}}}
        return label,box
    def test_two_explicit_starters(self):
        l,b=self.data()
        r=extract(l,b,{"url":"official","sha256":"a"*64})
        self.assertTrue(r["verified_starters"])
        self.assertEqual(r["teams"]["home"]["starter_id"],10)
    def test_no_guess_from_order(self):
        l,b=self.data();del b["playerByGameStats"]["awayTeam"]["goalies"][0]["starter"]
        self.assertFalse(extract(l,b,{})["verified_starters"])
    def test_reject_date_mismatch(self):
        l,b=self.data();b["gameDate"]="2026-10-08"
        with self.assertRaises(ValueError):extract(l,b,{})
    def test_reject_duplicate_goalie(self):
        l,b=self.data();b["playerByGameStats"]["homeTeam"]["goalies"]*=2
        with self.assertRaises(ValueError):extract(l,b,{})
    def test_capture_cache(self):
        l,b=self.data();calls=[]
        def fetcher(gid):
            calls.append(gid)
            return b,{"url":"official","sha256":"a"*64}
        with tempfile.TemporaryDirectory() as d:
            first=capture([l],d,fetcher)
            second=capture([l],d,fetcher)
            self.assertEqual(first["with_explicit_starters"],1)
            self.assertEqual(second["records"][0]["status"],"cached")
            self.assertEqual(len(calls),1)
    def test_no_false_completion(self):
        l,b=self.data()
        with tempfile.TemporaryDirectory() as d:
            result=capture([l],d,lambda _:(_ for _ in ()).throw(OSError("offline")))
            self.assertEqual(result["with_explicit_starters"],0)
            self.assertEqual(result["records"][0]["status"],"blocked_OSError")
if __name__=="__main__":unittest.main()
