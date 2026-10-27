import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from possession_intelligence import build,markdown
class Tests(unittest.TestCase):
 def test_pace_and_combined_possessions(self):
  snapshot={"content_sha256":"x","predictions":[{"game_id":"future","tipoff_utc":"2026-10-30T01:00:00Z","home_team":"DEN","away_team":"GS"}]}
  hist=[];obs=[]
  for i in range(3):
   gid=str(i)
   hist.append({"game_id":gid,"tipoff_utc":f"2026-10-2{i+1}T00:00:00Z","home_team":"DEN","away_team":"GS"})
   for team,opp in (("DEN","GS"),("GS","DEN")):
    obs.append({"game_id":gid,"tipoff_utc":hist[-1]["tipoff_utc"],"team":team,"opponent":opp,"possessions_estimated":100.0,"points":110})
  report=build(snapshot,hist,{"postgame_history_only":True,"games":obs})
  g=report["games"]["future"]
  self.assertEqual(g["projected_game_pace"],100.0)
  self.assertEqual(g["projected_combined_team_possessions"],200.0)
  self.assertEqual(g["projections"]["DEN"]["projected_points"],110.0)
  self.assertIn("Total de posesiones",markdown(report))
if __name__=="__main__":unittest.main()
