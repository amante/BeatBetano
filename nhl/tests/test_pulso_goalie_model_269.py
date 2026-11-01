import unittest
from datetime import date,timedelta
from nhl.pulso_goalie_model_269 import evaluate,split,score,train,predict
class GoalieModel269(unittest.TestCase):
 def sample(self):
  rows=[]
  for i in range(600):
   d=(date(2024,10,1)+timedelta(days=i)).isoformat()
   prior=(date(2024,9,30)+timedelta(days=i)).isoformat()
   rows.append({"game_id":str(i),"date":d,"feature_as_of_date":prior,
    "ml_winner":"home" if i%3 else "away",
    "home_goalie_prior_sv":.88+(i%10)/500,
    "away_goalie_prior_sv":.89+(i%8)/500,
    "home_team_prior_strength":(i%7-3)/10,
    "away_team_prior_strength":(i%5-2)/10})
  return {"kind":"nhl_historical_goalie_features_267","source_game_count":2811,
  "batch_report":{"complete_source_coverage":True},"eligible_rows":rows,
  "eligible_count":len(rows),"calibrated":False,"odds_used":False}
 def test_eval_finite_chronological(self):
  r=evaluate(self.sample())
  self.assertEqual(r["fit_n"]+r["validation_n"]+r["holdout_n"],600)
  self.assertFalse(r["automatic_promotion"])
  self.assertGreater(r["calibrated_holdout"]["log_loss"],0)
 def test_holdout_labels_do_not_change_fit(self):
  a=self.sample();b=self.sample()
  for r in b["eligible_rows"][-80:]:r["ml_winner"]="away" if r["ml_winner"]=="home" else "home"
  x=evaluate(a);y=evaluate(b)
  self.assertEqual(x["raw_model"],y["raw_model"])
  self.assertEqual(x["validation_platt_model"],y["validation_platt_model"])
 def test_leakage_rejected(self):
  a=self.sample();a["eligible_rows"][0]["feature_as_of_date"]=a["eligible_rows"][0]["date"]
  with self.assertRaises(ValueError):evaluate(a)
 def test_missing_data_rejected(self):
  a=self.sample();a["batch_report"]["complete_source_coverage"]=False
  with self.assertRaises(ValueError):evaluate(a)
 def test_probability_bounds(self):
  model=train([[.1],[.5],[.9]],[0,0,1],steps=100)
  self.assertTrue(0<predict(model,[.8])<1)
if __name__=="__main__":unittest.main()
