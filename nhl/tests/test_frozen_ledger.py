import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frozen_ledger import freeze,join
S={"sport":"nhl","as_of_utc":"2026-10-26T12:00:00Z","events":[{"event_id":"123","start_utc":"2026-10-27T00:00:00Z","home_team":"BOS","away_team":"TOR","statistical_p_home":.51}]}
G={"sport":"nhl","as_of_utc":S["as_of_utc"],"games":{}}
class Test(unittest.TestCase):
 def test_freeze_does_not_invent_goalie(self):
  x=freeze(S,G,["official"])
  self.assertFalse(x["games"][0]["starter_confirmed_at_freeze"])
  self.assertFalse(x["postgame_outcomes_included"])
 def test_postgame_join_preserves_frozen(self):
  x=freeze(S,G,["official"])
  y=join(x,{"games":[{"event_id":"123","game_state":"FINAL","home_score":2,"away_score":1,"home_team":"BOS","away_team":"TOR"}]})
  self.assertEqual(y["joined_results"][0]["home_won"],1)
  self.assertFalse(y["historical_goalie_holdout_run"])
 def test_digest_detects_change(self):
  x=freeze(S,G,["official"]);x["games"][0]["statistical_p_home"]=.99
  with self.assertRaises(ValueError):join(x,{"games":[]})
 def test_team_mismatch_rejected(self):
  x=freeze(S,G,[])
  with self.assertRaises(ValueError):join(x,{"games":[{"event_id":"123","game_state":"FINAL","home_score":1,"away_score":2,"home_team":"TOR","away_team":"BOS"}]})
if __name__=="__main__":unittest.main()
