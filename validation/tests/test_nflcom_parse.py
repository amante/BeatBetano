import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nflcom_parse import parse_tables
class Tests(unittest.TestCase):
    def test_structured_report_rows(self):
        html='''<table><thead><tr><th>Player</th><th>Position</th><th>Game Status</th></tr></thead>
        <tbody><tr><td>Jane Example</td><td>CB</td><td>Questionable</td></tr>
        <tr><td>John Example</td><td>S</td><td>Out</td></tr></tbody></table>'''
        d=parse_tables(html)
        self.assertEqual(d.game_status.tolist(),["QUESTIONABLE","OUT"])
    def test_unstructured_page_fails_closed(self):
        self.assertTrue(parse_tables("<html><div>Loading...</div></html>").empty)
if __name__=="__main__":unittest.main()
