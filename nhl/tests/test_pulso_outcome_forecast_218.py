import unittest
from nhl.pulso_outcome_forecast_218 import generate,VERSION
class Forecast218(unittest.TestCase):
 def setup_history(self):
  rows=[]
  from datetime import date,timedelta
  for i in range(210):
   rows.append({"game_id":str(i),"date":(date(2025,10,1)+timedelta(days=i)).isoformat(),
    "home":"EDM","away":"COL","ml_winner":"home","rt_result":"home",
    "first_to_plus3":"home","home_reached_plus3":"True","away_reached_plus3":"False"})
  return rows
 def test_frozen_five_markets(self):
  game={"game_id":"future1","home":"EDM","away":"COL","start_utc":"2026-11-30T23:00:00Z"}
  frozen=generate([game],self.setup_history(),"2026-11-29T13:00:00Z","a"*64)
  self.assertEqual(len(frozen),5)
  self.assertTrue(all(x["record"]["model_version"]==VERSION for x in frozen))
  self.assertTrue(all(x["record"]["official"] is False for x in frozen))
 def test_future_and_same_date_history_does_not_change_forecast(self):
  game={"game_id":"future2","home":"EDM","away":"COL","start_utc":"2026-11-30T23:00:00Z"}
  history=self.setup_history()
  prior=generate([game],history,"2026-11-29T13:00:00Z","a"*64)
  history.append({**history[0],"game_id":"future-game","date":"2026-11-30","ml_winner":"away"})
  after=generate([game],history,"2026-11-29T13:00:00Z","a"*64)
  self.assertEqual(prior,after)
 def test_no_predictions_for_already_started_game(self):
  game={"game_id":"1","home":"EDM","away":"COL","start_utc":"2026-11-28T20:00:00Z"}
  self.assertEqual(generate([game],self.setup_history(),"2026-11-29T13:00:00Z","a"*64),[])
 def test_duplicate_fixtures_are_rejected(self):
  game={"game_id":"1","home":"EDM","away":"COL","start_utc":"2026-11-30T23:00:00Z"}
  with self.assertRaises(ValueError):generate([game,game],self.setup_history(),"2026-11-29T13:00:00Z","a"*64)
if __name__=="__main__":unittest.main()
