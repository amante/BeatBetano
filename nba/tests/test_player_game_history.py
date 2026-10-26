import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player_game_history import parse_boxscore,collect

def fixture():
    return {"game_id":"123","home_team":"BOS","away_team":"NYK",
            "tipoff_utc":"2026-01-02T20:00:00Z"}
def payload():
    return {"header":{"competitions":[{"id":"123",
       "status":{"type":{"completed":True}},
       "competitors":[{"team":{"abbreviation":"BOS"}},{"team":{"abbreviation":"NYK"}}]}]},
       "boxscore":{"players":[
       {"team":{"abbreviation":"BOS"},"statistics":[{"labels":["MIN","PTS"],"athletes":[
         {"athlete":{"id":"1","displayName":"A"},"stats":["31:30","20"],"starter":True}]}]},
       {"team":{"abbreviation":"NYK"},"statistics":[{"labels":["MIN","PTS"],"athletes":[
         {"athlete":{"id":"2","displayName":"B"},"stats":["20:00","8"],"starter":False}]}]}]}}

class Tests(unittest.TestCase):
    def test_player_minutes_and_postgame_only(self):
        out=parse_boxscore(payload(),fixture(),"2026-01-03T00:00:00Z")
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]["minutes_played"],31.5)
        self.assertFalse(out[0]["availability_known_pregame"])
    def test_reject_wrong_game(self):
        p=payload();p["header"]["competitions"][0]["id"]="999"
        with self.assertRaises(ValueError):parse_boxscore(p,fixture(),"now")
    def test_reject_noncompleted(self):
        p=payload();p["header"]["competitions"][0]["status"]["type"]["completed"]=False
        with self.assertRaises(ValueError):parse_boxscore(p,fixture(),"now")
    def test_reject_duplicate_player(self):
        p=payload()
        p["boxscore"]["players"][0]["statistics"][0]["athletes"].append(
            dict(p["boxscore"]["players"][0]["statistics"][0]["athletes"][0]))
        with self.assertRaises(ValueError):parse_boxscore(p,fixture(),"now")
if __name__=="__main__":unittest.main()
