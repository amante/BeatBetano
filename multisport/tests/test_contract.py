import unittest
from multisport.contract import validate_report

def report(sport="nba"):
    return {"sport":sport,"as_of_utc":"2026-10-25T12:00:00Z",
      "odds_used_in_sport_model":False,
      "events":[{"event_id":"1","start_utc":"2026-10-25T19:00:00Z",
        "participants":["A","B"],"official_baseline":.55,
        "challenger":None,"final_probability":None}]}

class ContractTests(unittest.TestCase):
    def test_each_sport_supports_pending_probability(self):
        for sport in ("nba","nfl","nhl","tennis","soccer"):
            self.assertEqual(validate_report(report(sport))["verified_probabilities"],0)
    def test_rejects_market_anchoring(self):
        r=report();r["odds_used_in_sport_model"]=True
        with self.assertRaises(ValueError):validate_report(r)
    def test_rejects_in_play(self):
        r=report();r["as_of_utc"]="2026-10-25T20:00:00Z"
        with self.assertRaises(ValueError):validate_report(r)
    def test_no_fake_final_without_validation(self):
        r=report();r["events"][0]["final_probability"]=.6
        with self.assertRaises(ValueError):validate_report(r)
    def test_soccer_final_three_way(self):
        r=report("soccer");e=r["events"][0]
        e.update(final_probability=.5,draw_probability=.3,away_probability=.2,
                 all_inputs_verified=True,independent_validation_passed=True,validation_report_ref="report.json")
        self.assertEqual(validate_report(r)["verified_probabilities"],1)
    def test_nba_complementary(self):
        r=report();e=r["events"][0]
        e.update(final_probability=.6,away_probability=.4,all_inputs_verified=True,
                 independent_validation_passed=True,validation_report_ref="report.json")
        self.assertEqual(validate_report(r)["verified_probabilities"],1)
    def test_duplicate_games_rejected(self):
        r=report();r["events"].append(dict(r["events"][0]))
        with self.assertRaises(ValueError):validate_report(r)

if __name__=="__main__":unittest.main()
