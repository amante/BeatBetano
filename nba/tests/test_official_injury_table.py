import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_injury_table import extract
from injury_lineup_joint import compile_report
class Tests(unittest.TestCase):
 def test_real_pdf_layout_continuation(self):
  rows=extract(["10/26/2026 07:00 (ET) MIN@CLE Minnesota Timberwolves NOT YET SUBMITTED\n"
    "Cleveland Cavaliers Diop, Khalifa Out\n"
    "Tomlin, Nae'Qwan Out\n"
    "WAS@CHA Washington Wizards Dybantsa, AJ Out\n"
    "Vukcevic, Tristan Out\n"
    "Charlotte Hornets White, Coby Out"])
  self.assertEqual([(r["team"],r["player"]) for r in rows],
   [("CLE","Khalifa Diop"),("CLE","Nae'Qwan Tomlin"),("WAS","AJ Dybantsa"),
    ("WAS","Tristan Vukcevic"),("CHA","Coby White")])
 def test_team_name_not_part_of_player(self):
  self.assertEqual(extract(["Boston Celtics Brown, Jaylen Questionable"])[0]["player"],"Jaylen Brown")
 def test_no_cross_page_inheritance(self):
  self.assertEqual(extract(["Cleveland Cavaliers Diop, Khalifa Out","Tomlin, Nae'Qwan Out"])[1:],[])
 def test_no_submitted_not_healthy(self):
  self.assertEqual(extract(["Minnesota Timberwolves NOT YET SUBMITTED"]),[])
 def test_no_late_report_backfill(self):
  snap={"created_at_utc":"2026-10-26T16:00:00Z","predictions":[{"game_id":"1","home_team":"CLE","away_team":"MIN"}]}
  official={"official_document_retrieved":True,"source_report_as_of_utc":"2026-10-26T16:00:00Z",
   "downloaded_at_utc":"2026-10-26T17:00:00Z","raw_page_text":["Cleveland Cavaliers Diop, Khalifa Out"]}
  self.assertEqual(compile_report(snap,official)["official_player_rows_resolved"],0)
if __name__=="__main__":unittest.main()
