import unittest
from copy import deepcopy
from nhl.pulso_goalie_scenarios_258 import MARKETS
from nhl.pulso_goalie_conditioned_259 import integrate

class GoalieConditioned259(unittest.TestCase):
    def source(self):
        return {"kind":"nhl_goalie_conditional_scenarios_258","as_of_utc":"2026-10-31T14:00:00Z",
                "odds_used":False,"games":[{"game_id":"1","home":"NSH","away":"BUF","scenario_count":1,
                "scenarios":[{"home_goalie":{"player_id":10,"name":"A"},"away_goalie":{"player_id":20,"name":"B"}}]}]}
    def model(self):
        probs={key:0.2 for key in MARKETS}
        probs.update({"ml_home":0.6,"ml_away":0.4,"rt_home":0.4,"rt_draw":0.2,"rt_away":0.4})
        return {"kind":"nhl_fitted_goalie_conditional_259","as_of_utc":"2026-10-31T14:00:00Z",
                "calibrated":True,"walk_forward_validated":True,"odds_used":False,
                "predictions":[{"game_id":"1","home":"NSH","away":"BUF","home_goalie_id":10,"away_goalie_id":20,
                "home_goalie_name":"A","away_goalie_name":"B","computed_at_utc":"2026-10-31T14:01:00Z",
                "start_utc":"2026-10-31T23:00:00Z","odds_used":False,"probabilities":probs}]}
    def test_missing_model_stays_null(self):
        r=integrate(self.source())
        self.assertEqual(r["blocked_scenarios"],1)
        self.assertEqual(r["official_predictions"],0)
        self.assertTrue(all(v is None for v in r["games"][0]["scenarios"][0]["probabilities"].values()))
    def test_fitted_conditional_passthrough(self):
        r=integrate(self.source(),self.model())
        self.assertEqual(r["validated_experimental_scenarios"],1)
        self.assertEqual(r["games"][0]["scenarios"][0]["probabilities"]["ml_home"],0.6)
    def test_reject_wrong_goalie(self):
        m=self.model();m["predictions"][0]["home_goalie_id"]=11
        with self.assertRaises(ValueError):integrate(self.source(),m)
    def test_reject_unverified_model(self):
        m=self.model();m["calibrated"]=False
        with self.assertRaises(ValueError):integrate(self.source(),m)
    def test_reject_bad_probability(self):
        m=self.model();m["predictions"][0]["probabilities"]["ml_home"]=0.9
        with self.assertRaises(ValueError):integrate(self.source(),m)
    def test_reject_postgame(self):
        m=self.model();m["predictions"][0]["computed_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):integrate(self.source(),m)

if __name__=="__main__":unittest.main()
