import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from historical_postgame_labels import labels

def game(goals,final=None):
    h=a=0;plays=[]
    for i,(side,period,ptype) in enumerate(goals):
        h+=side=="home";a+=side=="away"
        plays.append({"event_id":i+1,"period":period,"period_type":ptype,
                      "time_in_period":f"01:{i:02d}",
                      "owner_team_id":10 if side=="home" else 20,
                      "home_score":h,"away_score":a})
    return {"game_id":101,"date":"2026-01-01","home":"BOS","away":"MTL",
       "result_final":{"home_goals":(final or (h,a))[0],"away_goals":(final or (h,a))[1]},
       "game_info":{},"boxscore":{"home_team":{"id":10},"away_team":{"id":20}},
       "goal_events":plays}

class LabelTests(unittest.TestCase):
 def test_regulation_and_first_to_three(self):
  x=labels(game([("home",1,"REG"),("home",1,"REG"),("home",2,"REG"),("away",3,"REG")]))
  self.assertEqual((x["rt_result"],x["ml_winner"],x["first_to_plus3"]),("home","home","home"))
  self.assertEqual((x["rt_home_goals"],x["rt_away_goals"]),(3,1))
 def test_ot_after_tie(self):
  x=labels(game([("home",1,"REG"),("away",2,"REG"),("away",4,"OT")]))
  self.assertEqual((x["rt_result"],x["ml_winner"],x["overtime_or_shootout"]),("draw","away",True))
 def test_shootout_final_goal(self):
  x=labels(game([("home",1,"REG"),("away",2,"REG")],final=(2,1)))
  self.assertTrue(x["shootout"])
  self.assertEqual((x["rt_result"],x["ml_winner"]),("draw","home"))
 def test_broken_score_rejected(self):
  g=game([("home",1,"REG"),("away",2,"REG"),("home",3,"REG")])
  g["goal_events"][1]["away_score"]=9
  with self.assertRaisesRegex(ValueError,"inconsistent"):labels(g)
 def test_missing_team_ids_rejected(self):
  g=game([("home",1,"REG")]);g["boxscore"]["home_team"]={}
  with self.assertRaisesRegex(ValueError,"team IDs"):labels(g)
if __name__=="__main__":unittest.main()
