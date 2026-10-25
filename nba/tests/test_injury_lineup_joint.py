import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injury_lineup_joint import compile_report,parse_lines,normalize_team
class Tests(unittest.TestCase):
    def test_parses_status_without_fabricated_athlete(self):
        rows=parse_lines(["BOS John Doe Questionable knee\nReport not yet submitted"])
        self.assertEqual(rows[0]["status_mentioned"],"Questionable")
        self.assertFalse(rows[0]["player_verified"])
    def test_preserves_no_confirmed_lineups(self):
        snap={"predictions":[{"game_id":"123","home_team":"GS","away_team":"NO"}]}
        out=compile_report(snap,{"raw_page_text":["Out"],"official_document_retrieved":True})
        g=out["games"]["123"]
        self.assertEqual((g["home_team"],g["away_team"]),("GSW","NOP"))
        self.assertIsNone(g["home_confirmed_starting_five"])
        self.assertFalse(g["official_player_team_status_confirmed"])
if __name__=="__main__":unittest.main()
