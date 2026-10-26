import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalie_impact_audit import evaluate
def r(i,goalie):
 return {"event_id":str(i),"team":"BOS","sport":"nhl","market":"moneyline",
  "goalie_id":goalie,"season_end_year":2026,
  "prediction_as_of_utc":"2025-11-01T12:00:00Z","tipoff_utc":"2025-11-01T23:00:00Z",
  "goalie_observed_at_utc":"2025-11-01T11:00:00Z","training_cutoff_utc":"2025-10-31T00:00:00Z",
  "goalie_confirmed_at_freeze":True,"sources_verified":True,"bookmaker_odds_used":False,
  "baseline_win_probability":.5,"team_won":i%2}
class Test(unittest.TestCase):
 def test_two_goalies_descriptive_only(self):
  x=evaluate([r(i,"A" if i<=3 else "B") for i in range(1,7)],min_pair_games=2)
  self.assertEqual(len(x["matched_team_season_goalie_diagnostics"]),2)
  self.assertFalse(x["independently_validated"])
 def test_late_evidence_rejected(self):
  x=r(1,"A");x["goalie_observed_at_utc"]="2025-11-02T00:00:00Z"
  with self.assertRaises(ValueError):evaluate([x],1)
 def test_not_confirmed_rejected(self):
  x=r(1,"A");x["goalie_confirmed_at_freeze"]=False
  with self.assertRaises(ValueError):evaluate([x],1)
 def test_duplicates_rejected(self):
  with self.assertRaises(ValueError):evaluate([r(1,"A"),r(1,"B")],1)
 def test_market_anchor_rejected(self):
  x=r(1,"A");x["bookmaker_odds_used"]=True
  with self.assertRaises(ValueError):evaluate([x],1)
if __name__=="__main__":unittest.main()
