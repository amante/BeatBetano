import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from team_units import team_units,game_units
AS="2026-10-26T10:00:00Z";TIP="2026-10-27T00:00:00Z"
def item(rating=70,observed=AS):
 return {"source_url":"https://nhl.com/official","source_verified":True,
         "observed_at_utc":observed,"rating":rating}
def inputs():
 return {"team":"BOS",**{k:item() for k in
 ("forwards","defense","supporting_cast","goalie","power_play","penalty_kill")}}
class Tests(unittest.TestCase):
 def test_complete_units_still_not_calibrated(self):
  x=team_units(inputs(),AS,TIP,"BOS")
  self.assertTrue(x["full_evidence"]);self.assertIsNone(x["crs"])
 def test_postfreeze_not_used(self):
  x=inputs();x["goalie"]=item(observed="2026-10-26T11:00:00Z")
  self.assertIn("goalie",team_units(x,AS,TIP,"BOS")["missing"])
 def test_missing_source(self):
  x=inputs();x["defense"].pop("source_url")
  self.assertIn("defense",team_units(x,AS,TIP,"BOS")["missing"])
 def test_independent_markets_undefined(self):
  b=inputs();b["team"]="TOR"
  x=game_units(inputs(),b,AS,TIP,"BOS","TOR")
  self.assertTrue(all(v is None for v in x["market_estimates"].values()))
 def test_team_mismatch(self):
  with self.assertRaises(ValueError):team_units(inputs(),AS,TIP,"TOR")
if __name__=="__main__":unittest.main()
