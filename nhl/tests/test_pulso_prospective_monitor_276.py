import unittest,tempfile,json
from pathlib import Path
from nhl.pulso_prospective_monitor_276 import freeze,score
class Prospective276(unittest.TestCase):
 def slate(self):
  return {"kind":"nhl_research_daily_presentation_275","date":"2026-11-01","official":False,"odds_used":False,
   "official_schedule_games":2,"games":[{"game_id":"1","home":"CAR","away":"WPG","start_utc":"2026-11-01T18:00:00Z","status":"experimental_forecast",
   "ml":{"home":.6,"away":.4},"rt":{"home":.4,"draw":.2,"away":.4},
   "home_plus3":.3,"away_plus3":.25,"first_to_plus3":{"home":.2,"away":.15,"none":.65}},
   {"game_id":"2","home":"NYR","away":"EDM","start_utc":"2026-11-01T23:00:00Z","status":"pregame_forecast_unavailable"}]}
 def result(self):
  return {"kind":"nhl_official_final_labels","source_url":"https://api-web.nhle.com/v1/gamecenter/1/landing",
  "source_as_of_utc":"2026-11-02T18:00:00Z","games":[{"game_id":"1","home":"CAR","away":"WPG","game_state":"OFF",
  "outcomes":{"ml":"home","rt":"home","home3":"yes","away3":"no","first3":"home"}}]}
 def test_freeze_and_score(self):
  with tempfile.TemporaryDirectory() as d:
   snap=freeze(self.slate(),123,d)
   self.assertEqual(score(snap,self.result())["markets"]["ml"]["n"],1)
   self.assertEqual(score(snap,self.result())["markets"]["ml"]["brier"],.16)
   self.assertFalse(score(snap,self.result())["automatic_promotion"])
   with self.assertRaises(FileExistsError):freeze(self.slate(),123,d)
 def test_tampered_record_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   snap=freeze(self.slate(),123,d);snap["slate"]["games"][0]["ml"]["home"]=.99
   with self.assertRaises(ValueError):score(snap,self.result())
 def test_no_unfinished_result(self):
  with tempfile.TemporaryDirectory() as d:
   snap=freeze(self.slate(),123,d);res=self.result();res["games"][0]["game_state"]="LIVE"
   with self.assertRaises(ValueError):score(snap,res)
 def test_missing_results_remain_pending(self):
  with tempfile.TemporaryDirectory() as d:
   snap=freeze(self.slate(),123,d);res=self.result();res["games"]=[]
   self.assertEqual(score(snap,res)["pending_games"],1)
if __name__=="__main__":unittest.main()
