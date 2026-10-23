import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import evaluate,score,dual_eligible
class Tests(unittest.TestCase):
    def game(self,**updates):
        g={"game_id":"G1","season":2023,"tipoff_utc":"2023-11-01T00:00:00Z",
           "home_team":"BOS","away_team":"NYK","home_points":110,"away_points":103}
        g.update(updates);return g
    def test_no_future_result_leakage(self):
        g1=self.game(home_points=100,away_points=50)
        g2=self.game(home_points=50,away_points=100)
        nextgame=self.game(game_id="G2",tipoff_utc="2023-11-03T00:00:00Z",home_points=None,away_points=None)
        first=list(evaluate([g1,nextgame]))[0]
        changed=list(evaluate([g2,nextgame]))[0]
        self.assertAlmostEqual(first.p_home,changed.p_home)
        self.assertNotAlmostEqual(list(evaluate([g1,nextgame]))[1].p_home,list(evaluate([g2,nextgame]))[1].p_home)
    def test_market_columns_are_ignored(self):
        a=list(evaluate([self.game(odds_home=1.5)]))[0]
        b=list(evaluate([self.game(odds_home=10000)]))[0]
        self.assertEqual(a.p_home,b.p_home)
    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            list(evaluate([self.game(),self.game()]))
    def test_dual_threshold(self):
        self.assertTrue(dual_eligible(.53))
        self.assertFalse(dual_eligible(.54))
    def test_scoring_completed_only(self):
        games=[self.game()]
        self.assertEqual(score(list(evaluate(games)),games)["n"],1)
if __name__=="__main__":unittest.main()
