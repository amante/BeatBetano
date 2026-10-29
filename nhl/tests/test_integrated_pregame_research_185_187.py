import unittest
from nhl.integrated_pregame_research_185_187 import assemble,context,baseline_probabilities
class IntegratedResearchTests(unittest.TestCase):
 def setup_case(self):
  p={"player_id":1,"unit":"top6","status":"projected","expected_share":1}
  lineup={"team":"BOS","source":"dated roster provider","as_of":"2026-10-28T12:00:00Z","players":[p]}
  history={"date":"2026-10-27","team":"BOS","players":{"1":{"role":"skater","observed":5,"goals":2,"shots":20}}}
  return {"as_of":"2026-10-28T16:00:00Z",
   "fixture":{"game_id":"g","home":"BOS","away":"MTL","start":"2026-10-28T23:00:00Z","venue_confirmed":True},
   "history":history,"baseline_lineup":lineup,"expected_lineup":lineup,
   "observations":[{"team":"BOS","kind":"pp","as_of":"2026-10-28T15:00:00Z","source":"official","chances":5,"conversions":1}],
   "historical_counts":{"cutoff_date":"2026-10-27","source":"historical outcome CSV",
    "global":{"ml":{"home":11,"away":9},"rt":{"home":7,"draw":6,"away":7},"first3":{"home":5,"away":6,"none":9},"home3":{"yes":8,"no":12},"away3":{"yes":9,"no":11}},
    "teams":{}}}
 def test_all_five_research_targets_no_promotion(self):
  r=assemble(self.setup_case())
  self.assertEqual(len(r["two_sided_probabilities_research"]),5)
  self.assertEqual(set(r["two_sided_probabilities_research"]["ml"]),{"home","away"})
  self.assertTrue(r["context_research"]["rivalry"])
  self.assertEqual(r["context_research"]["special_teams"]["BOS"]["pp"]["beta_shrunk"],.2)
  self.assertEqual(r["crs_research"]["units"]["top6"]["expected"]["offense_proxy"],.6)
  self.assertIsNone(r["official_model_outputs"])
  self.assertFalse(r["probabilities_validated"])
 def test_future_sources_blocked(self):
  s=self.setup_case()
  s["observations"][0]["as_of"]="2026-10-29T00:00:00Z"
  with self.assertRaises(ValueError):assemble(s)
 def test_outcome_counts_cannot_include_target_day(self):
  s=self.setup_case();s["historical_counts"]["cutoff_date"]="2026-10-28"
  with self.assertRaises(ValueError):assemble(s)
 def test_missing_roster_evidence_does_not_look_complete(self):
  s=self.setup_case();s["history"]["players"]={}
  r=assemble(s)
  self.assertIsNone(r["crs_research"]["units"]["top6"]["expected"]["offense_proxy"])
  self.assertIsNone(r["crs_research"]["availability"]["availability_delta_skater_offense_proxy"])
if __name__=="__main__":unittest.main()
