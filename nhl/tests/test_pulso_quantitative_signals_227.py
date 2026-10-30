import unittest
from nhl.pulso_quantitative_signals_227 import compute
class Test227(unittest.TestCase):
 def setUp(self):
  self.bridge={"kind":"sporting_source_bridge","games":{"1":{"game_id":"1","home":"EDM","away":"CGY",
   "as_of":"2026-10-29T20:00:00Z","start_utc":"2026-10-30T00:00:00Z",
   "teams":{"EDM":{"provider_goalie_id_observed":42},"CGY":{"provider_goalie_id_observed":43}}}}}
 def test_absent_source_null_not_invented(self):
  r=compute(self.bridge,{})["games"]["1"]
  self.assertFalse(r["sporting_signals_complete"])
  self.assertEqual(r["teams"]["EDM"]["signals"],{})
 def test_valid_inputs(self):
  stamp={"as_of":"2026-10-29T19:00:00Z","source_url":"https://api-web.nhle.com"}
  inp={"crs":{**stamp,"availability_independently_verified":True,"lineup_identity_verified":True,
                 "offense_proxy":1.2,"availability_delta":-.3},
       "goalie":{**stamp,"goalie_player_id":42,"identity_independently_verified":True,
                  "prior_games":8,"prior_saves":230,"prior_shots":250},
       "special_teams":{**stamp,"events_prior_to_capture":True,"powerplay_goals":12,
                   "powerplay_opportunities":60,"opponent_powerplay_goals":8,"times_shorthanded":55}}
  r=compute(self.bridge,{"1":{"EDM":inp}})["games"]["1"]["teams"]["EDM"]
  self.assertTrue(r["sporting_ready"])
  self.assertAlmostEqual(r["signals"]["special_teams"]["pp"]["shrunk"],14/70)
 def test_post_capture_data_excluded(self):
  r=compute(self.bridge,{"1":{"EDM":{"crs":{"as_of":"2026-10-29T21:00:00Z",
    "source_url":"https://api-web.nhle.com","availability_independently_verified":True,
    "lineup_identity_verified":True,"offense_proxy":2,"availability_delta":1}}}})["games"]["1"]
  self.assertNotIn("crs",r["teams"]["EDM"]["signals"])
if __name__=="__main__":unittest.main()
