import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lineup_source_cascade import cascade
S={"content_sha256":"abc","created_at_utc":"2026-10-26T22:00:00Z","predictions":[{"game_id":"9","home_team":"MIL","away_team":"IND","tipoff_utc":"2026-10-26T23:00:00Z"}]}
def cand(provider,status,starters=None,at="2026-10-26T21:30:00Z"):
 return {"game_id":"9","team":"MIL","provider":provider,"status":status,"starters":starters or ["A","B","C","D","E"],"source_url":"https://example.org/lineup","observed_at_utc":at}
class Tests(unittest.TestCase):
 def test_falls_back_to_projected(self):
  r=cascade(S,{"candidates":[cand("rotowire","projected")]})
  a=r["games"]["9"]["teams"]["MIL"]
  self.assertEqual(a["lineup_status"],"projected")
  self.assertEqual(a["source_provider"],"rotowire")
  self.assertFalse(a["is_official_confirmation"])
 def test_official_confirmation_beats_projection(self):
  rows=[cand("rotowire","projected"),cand("nba_official","confirmed")]
  self.assertEqual(cascade(S,{"candidates":rows})["games"]["9"]["teams"]["MIL"]["source_provider"],"nba_official")
 def test_post_tip_ignored(self):
  x=cand("rotowire","projected",at="2026-10-26T23:10:00Z")
  self.assertEqual(cascade(S,{"candidates":[x]})["games"]["9"]["teams"]["MIL"]["lineup_status"],"unavailable")
 def test_conflict_visible(self):
  x=cand("espn","projected",["X","B","C","D","E"])
  x["source_url"]="https://espn.com"
  r=cascade(S,{"candidates":[cand("rotowire","projected"),x]})
  self.assertFalse(r["games"]["9"]["teams"]["MIL"]["sources_consistent"])
if __name__=="__main__":unittest.main()
