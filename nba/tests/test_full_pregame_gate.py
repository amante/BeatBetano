import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from full_pregame_gate import review,REQUIRED
class Tests(unittest.TestCase):
    def snap(self):
        return {"content_sha256":"sha","predictions":[{"game_id":"1",
          "home_team":"BOS","away_team":"NYK","elo_p_home":.61,
          "challenger_p_home":.65,"hybrid_p_home":.61}]}
    def test_missing_evidence_fails_closed(self):
        r=review(self.snap())
        self.assertFalse(r["all_games_final_approved"])
        self.assertFalse(r["games"][0]["eligible_for_bet"])
        self.assertIsNone(r["games"][0]["final_p_home"])
        self.assertEqual(len(r["games"][0]["evidence_checks"]),7)
    def test_even_complete_inputs_require_calibrated_adjustment(self):
        data={k:{"verified":True,"source":"official","observed_at_utc":"2026-10-25T19:00:00Z"}
              for k in REQUIRED}
        data["availability_impact"]["home_win_probability_delta"]=.02
        r=review(self.snap(),{"games":{"1":data}})
        self.assertTrue(r["games"][0]["evidence_verified"])
        self.assertFalse(r["games"][0]["final_model_approved"])
        self.assertEqual(r["games"][0]["status"],"impact_calibration_required")
if __name__=="__main__":unittest.main()
