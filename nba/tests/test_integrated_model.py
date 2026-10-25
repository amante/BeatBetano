import hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integrated_model import integrate
from full_pregame_gate import REQUIRED

class Tests(unittest.TestCase):
    def setup(self):
        d={"created_at_utc":"2026-10-25T18:00:00+00:00",
           "predictions":[{"game_id":"abc","tipoff_utc":"2026-10-25T22:00:00Z",
               "home_team":"BOS","away_team":"NYK",
               "elo_p_home":.6,"challenger_p_home":.65,"hybrid_p_home":.6}]}
        d["content_sha256"]=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return d
    def evidence(self):
        x={k:{"verified":True,"source":"source-id","observed_at_utc":"2026-10-25T17:55:00Z"} for k in REQUIRED}
        x["availability_impact"].update({"log_odds_delta":.2,
          "calibration":{"model_version":"v1","report_ref":"holdout/locked.json","independent_holdout_passed":True}})
        return {"games":{"abc":x}}
    def test_missing_steps_no_fake_final(self):
        r=integrate(self.setup(),{})
        self.assertIsNone(r["predictions"][0]["integrated_p_home"])
    def test_integrated_when_validated_and_pre_tipoff(self):
        r=integrate(self.setup(),self.evidence())
        self.assertTrue(.6<r["predictions"][0]["integrated_p_home"]<.7)
        self.assertFalse(r["predictions"][0]["eligible_for_bet"])
    def test_post_snapshot_evidence_rejected(self):
        e=self.evidence();e["games"]["abc"]["injury_report"]["observed_at_utc"]="2026-10-25T18:05:00Z"
        r=integrate(self.setup(),e)
        self.assertIsNone(r["predictions"][0]["integrated_p_home"])
    def test_no_calibration_no_final(self):
        e=self.evidence();e["games"]["abc"]["availability_impact"]["calibration"]={}
        self.assertIsNone(integrate(self.setup(),e)["predictions"][0]["integrated_p_home"])
    def test_snapshot_tampering_rejected(self):
        s=self.setup();s["predictions"][0]["hybrid_p_home"]=.9
        with self.assertRaises(ValueError):integrate(s,{})
if __name__=="__main__":unittest.main()
