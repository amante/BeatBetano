import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rotation_efficiency_report import build
class Tests(unittest.TestCase):
 def test_unordered_history_uses_latest_five_chronologically(self):
  snap={"content_sha256":"abc","predictions":[{"game_id":"p","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-11-01T00:00:00Z"}]}
  history=[{"game_id":str(i),"tipoff_utc":f"2026-10-{i+10:02d}T00:00:00Z"} for i in range(6)]
  rows=[{"game_id":str(i),"team":"BOS","player_id":"9","player":"Example","minutes_played":10+i*2,"did_not_play":False} for i in reversed(range(6))]
  result=build(snap,history,{"players":rows})["games"]["p"]["teams"]["BOS"]
  self.assertEqual(result["provisional_rotation"][0]["minutes_projection"],16)
  self.assertEqual(result["players_with_minutes_estimates"],1)
  self.assertEqual(result["sampled_players"],1)
  self.assertEqual(result["players_below_minimum_sample"],0)
 def test_empty_sample_explicit(self):
  snap={"content_sha256":"abc","predictions":[{"game_id":"p","home_team":"BOS","away_team":"NYK","tipoff_utc":"2026-11-01T00:00:00Z"}]}
  r=build(snap,[],{"players":[]})["games"]["p"]["teams"]["BOS"]
  self.assertEqual(r["sampled_players"],0)
  self.assertEqual(r["players_with_minutes_estimates"],0)
if __name__=="__main__":unittest.main()
