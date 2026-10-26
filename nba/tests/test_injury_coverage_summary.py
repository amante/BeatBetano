import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injury_coverage_summary import summarize,markdown
class Tests(unittest.TestCase):
 def test_candidate_rows_are_not_verified(self):
  r=summarize({"official_document_retrieved":True},
   {"games":{"1":{"source_time_validated":True,"official_structured_candidate_rows":[{"player":"A"}],"lineups_confirmed":False}}},
   {"games":1,"complete_pregame_features":0})
  self.assertEqual(r["parsed_official_candidate_rows"],1)
  self.assertEqual(r["independently_verified_player_rows"],0)
  self.assertIn("0 of 9",markdown(r))
 def test_disagreeing_slates_rejected(self):
  with self.assertRaises(ValueError):summarize({},{"games":{}},{"games":2})
if __name__=="__main__":unittest.main()
