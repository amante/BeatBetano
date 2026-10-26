import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from impact_validation import evaluate

def row(i,season):
    return {"game_id":str(season)+"-"+str(i),"season_end_year":season,
        "tipoff_utc":str(season-1)+"-11-20T20:00:00Z",
        "prediction_as_of_utc":str(season-1)+"-11-20T18:00:00Z",
        "feature_observed_at_utc":str(season-1)+"-11-20T17:00:00Z",
        "model_training_cutoff_utc":str(season-1)+"-10-01T00:00:00Z",
        "features_point_in_time_verified":True,
        "impact_model_version":"candidate1","training_dataset_hash":"hash",
        "baseline_p_home":0.5,"candidate_p_home":0.6,"home_won":1}

class TestImpactValidation(unittest.TestCase):
    def test_held_out_improvement_does_not_certify(self):
        x=[row(i,s) for s in (2025,2026) for i in range(3)]
        report=evaluate(x,min_holdout=3)
        self.assertTrue(report["improved_all_holdouts"])
        self.assertFalse(report["independent_validation_passed"])
    def test_reject_future_features(self):
        x=[row(i,s) for s in (2025,2026) for i in range(3)]
        x[0]["feature_observed_at_utc"]=x[0]["tipoff_utc"]
        with self.assertRaises(ValueError):
            evaluate(x,min_holdout=3)
    def test_reject_small_sample(self):
        with self.assertRaises(ValueError):
            evaluate([row(1,2025),row(1,2026)],min_holdout=3)
    def test_reject_duplicate(self):
        x=[row(i,s) for s in (2025,2026) for i in range(3)]
        x.append(dict(x[0]))
        with self.assertRaises(ValueError):
            evaluate(x,min_holdout=3)

if __name__=="__main__":
    unittest.main()
