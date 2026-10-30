import unittest
from nhl.pulso_sporting_challenger_238 import prepare,split,train,predict,run
class Challenger238(unittest.TestCase):
 def row(self,i):
  f={"past_games":10,"prior_goalie_save_pct":.91,"prior_skater_goals_per_observed_game":3.1}
  a={"past_games":10,"prior_goalie_save_pct":.89,"prior_skater_goals_per_observed_game":2.8}
  return {"game_id":str(i),"date":"2025-%02d-%02d"%(1+i//300,1+i%28),
          "features":{"home":f,"away":a},"target":{"ml_winner":"home" if i%2 else "away"}}
 def test_train_and_predict(self):
  rows=[{"x":[i%2*.02,i%3*.2],"y":i%2} for i in range(20)]
  m=train(rows,epochs=30)
  self.assertTrue(0<predict(m,rows[0])<1)
 def test_chronological_guard(self):
  rows=[{"date":"2025-01-01","game_id":str(i),"x":[0,0],"y":i%2} for i in range(100)]
  with self.assertRaises(ValueError):split(rows)
 def test_missing_core_excluded(self):
  row=self.row(1)
  row["features"]["home"]={**row["features"]["home"],"prior_goalie_save_pct":None}
  x,reject=prepare([row])
  self.assertEqual(len(x),0)
  self.assertEqual(reject["missing_or_invalid_core"],1)
 def test_missing_audit_blocked(self):
  with self.assertRaises(ValueError):run([],{"status":"unknown","games":0})
 def test_same_day_separated_by_date(self):
  rows=[{"date":"2025-01-%02d"%d,"game_id":str(d*100+i),"x":[.1,.2],"y":i%2}
        for d in range(1,21) for i in range(30)]
  a,b,cut=split(rows)
  self.assertLess(max(r["date"] for r in a),min(r["date"] for r in b))
if __name__=="__main__":unittest.main()
