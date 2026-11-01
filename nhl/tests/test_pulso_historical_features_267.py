import unittest
from nhl.pulso_historical_features_267 import produce

def fixture(gid,day,home,away,winner,home_id=10,away_id=20):
    label={"game_id":str(gid),"date":day,"home":home,"away":away,"ml_winner":winner}
    def side(pid):
        return {"starter_id":pid,"goalies":[{"player_id":pid,"explicit_starter":True,
                   "source_row":{"saves":18,"shotsAgainst":20}}]}
    record={"game_id":str(gid),"date":day,"home":home,"away":away,"verified_starters":True,
            "teams":{"home":side(home_id),"away":side(away_id)}}
    return label,record

class Hist267(unittest.TestCase):
 def test_same_day_does_not_leak(self):
    a,b=fixture(1,"2026-10-01","BOS","MTL","home")
    c,d=fixture(2,"2026-10-01","BOS","MTL","away")
    result=produce([a,c],[b,d],min_goalie_shots=0,min_team_games=0)
    self.assertEqual(result["eligible_count"],0)
 def test_prior_dates_enable_features(self):
    items=[fixture(i,f"2026-10-{i:02d}","BOS","MTL","home") for i in range(1,8)]
    result=produce([p[0] for p in items],[p[1] for p in items],min_goalie_shots=50,min_team_games=2)
    self.assertEqual(result["eligible_count"],4)
    self.assertAlmostEqual(result["eligible_rows"][0]["home_goalie_prior_sv"],0.9)
    self.assertEqual(result["eligible_rows"][0]["feature_as_of_date"],"2026-10-03")
 def test_missing_evidence_blocks(self):
    l,r=fixture(1,"2026-10-01","BOS","MTL","home")
    result=produce([l],[])
    self.assertEqual(result["blocked_fixtures"][0]["reason"],"boxscore_missing")
 def test_no_starter_guess(self):
    l,r=fixture(1,"2026-10-01","BOS","MTL","home")
    r["verified_starters"]=False
    self.assertEqual(produce([l],[r])["blocked_fixtures"][0]["reason"],"no_explicit_both_starters")
 def test_fixture_mismatch_fatal(self):
    l,r=fixture(1,"2026-10-01","BOS","MTL","home")
    r["away"]="TOR"
    with self.assertRaises(ValueError):produce([l],[r])
 def test_duplicate_games_fatal(self):
    l,r=fixture(1,"2026-10-01","BOS","MTL","home")
    with self.assertRaises(ValueError):produce([l,l],[r])
if __name__=="__main__":unittest.main()
