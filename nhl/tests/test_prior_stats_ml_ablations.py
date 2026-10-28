import unittest
from nhl.prior_stats_ml_ablations import prepare,probability,measure
class PriorStatsAblationTests(unittest.TestCase):
 def test_joins_only_matched_prior_evidence(self):
  labels=[{"game_id":"1","date":"2026-03-02"}]
  good=[{"game_id":"1","date":"2026-03-02","source_class":"earlier_dates_postgame_boxscores_only",
         "home":{"prior_goalie_save_pct":.91,"prior_skater_goals_per_observed_game":3.2,
                 "pregame_starter_confirmed":False,"pregame_roster_confirmed":False},
         "away":{"prior_goalie_save_pct":.89,"prior_skater_goals_per_observed_game":2.8,
                 "pregame_starter_confirmed":False,"pregame_roster_confirmed":False}}]
  x=prepare(labels,good)
  self.assertAlmostEqual(x["1"]["goalie"],.02)
  self.assertAlmostEqual(x["1"]["skater"],.4)
  bad=[dict(good[0],date="2026-03-03")]
  with self.assertRaisesRegex(ValueError,"Unverified"):prepare(labels,bad)
 def test_absent_inputs_do_not_impute(self):
  x={"goalie":None,"skater":None}
  self.assertAlmostEqual(probability(.57,x,{"goalie":4.,"skater":.2}),.57)
 def test_binary_scoring(self):
  data=[{"game_id":"1","probs":{"ml":[.6,.4]},"y":{"ml":"home"}}]
  m=measure(data,{"1":{"goalie":None,"skater":None}},{"goalie":0.,"skater":0.})
  self.assertAlmostEqual(m["brier"],.16)
if __name__=="__main__":unittest.main()
