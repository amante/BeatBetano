import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from player_history_coverage import audit

def ledger():
    return [{"game_id":"1","home_team":"BOS","away_team":"NYK"}]
def sample():
    return {"games_requested":1,"source":"ESPN","players":[
       {"game_id":"1","team":"BOS","player_id":"a","minutes_played":35,
        "availability_known_pregame":False},
       {"game_id":"1","team":"NYK","player_id":"b","minutes_played":20,
        "availability_known_pregame":False}],"unavailable_games":[]}

class Tests(unittest.TestCase):
    def test_coverage_is_sample_only(self):
        a=audit(ledger(),sample())
        self.assertEqual(a["sample_coverage_fraction"],1)
        self.assertEqual(a["sample_two_team_boxscores"],1)
        self.assertFalse(a["impact_model_training_authorized"])
        self.assertFalse(a["historical_pregame_availability_verified"])
    def test_failure_count(self):
        s={"games_requested":1,"players":[],"unavailable_games":[{"game_id":"1","error_type":"HTTPError"}]}
        self.assertEqual(audit(ledger(),s)["sample_games_failed"],1)
    def test_leakage_flag_rejected(self):
        s=sample();s["players"][0]["availability_known_pregame"]=True
        with self.assertRaisesRegex(ValueError,"falsely"):
            audit(ledger(),s)
    def test_duplicate_failure_rejected(self):
        s=sample();s["unavailable_games"]=[{"game_id":"1"}]
        with self.assertRaises(ValueError):audit(ledger(),s)
if __name__=="__main__":unittest.main()
