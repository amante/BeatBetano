import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rotation_efficiency_report import build
def data():
 snap={"content_sha256":"abc","predictions":[{"game_id":"future","away_team":"BOS","home_team":"NYK","tipoff_utc":"2026-11-01T01:00:00Z"}]}
 history=[{"game_id":str(i),"tipoff_utc":f"2026-10-{i+10:02d}T01:00:00Z"} for i in range(3)]
 players={"players":[{"game_id":str(i),"team":"BOS","player_id":"a","player":"Athlete One","minutes_played":30+i,"did_not_play":False} for i in range(3)]}
 return snap,history,players
class Tests(unittest.TestCase):
 def test_minutes_and_missing_efficiency(self):
  x=build(*data());t=x["games"]["future"]["teams"]["BOS"]
  self.assertEqual(t["provisional_rotation"][0]["minutes_projection"],31)
  self.assertIsNone(t["offensive_rating"]);self.assertIsNone(t["scoring_possession_rate_pct"])
  self.assertFalse(x["games"]["future"]["current_starters_confirmed"])
 def test_no_future_boxscore_leakage(self):
  a,b,c=data();b[2]["tipoff_utc"]="2026-11-03T01:00:00Z"
  t=build(a,b,c)["games"]["future"]["teams"]["BOS"]["provisional_rotation"][0]
  self.assertIsNone(t["minutes_projection"])
 def test_tiny_sample_not_projection(self):
  a,b,c=data();c["players"]=c["players"][:1]
  self.assertIsNone(build(a,b,c)["games"]["future"]["teams"]["BOS"]["provisional_rotation"][0]["minutes_projection"])
if __name__=="__main__":unittest.main()
