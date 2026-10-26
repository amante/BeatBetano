import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lineup_live_collector import parse_rotowire
SNAP={"predictions":[{"game_id":"123","away_team":"IND","home_team":"MIL"}]}
HTML='<div class="lineup"><div class="lineup__abbr">IND</div><div class="lineup__abbr">MIL</div><ul class="lineup__list"><li class="lineup__player"><a>One</a></li><li class="lineup__player"><a>Two</a></li><li class="lineup__player"><a>Three</a></li><li class="lineup__player"><a>Four</a></li><li class="lineup__player"><a>Five</a></li></ul><ul class="lineup__list"><li class="lineup__player"><a>Six</a></li><li class="lineup__player"><a>Seven</a></li><li class="lineup__player"><a>Eight</a></li><li class="lineup__player"><a>Nine</a></li><li class="lineup__player"><a>Ten</a></li></ul></div>'
class Tests(unittest.TestCase):
 def test_both_teams(self):
  rows,errors=parse_rotowire(HTML,SNAP,"2026-10-26T22:00:00Z")
  self.assertEqual([x["team"] for x in rows],["IND","MIL"])
  self.assertEqual(rows[0]["status"],"projected")
 def test_unrecognized_html_no_fabrication(self):
  rows,errors=parse_rotowire("<html>Changed selectors</html>",SNAP,"2026-10-26T22:00:00Z")
  self.assertEqual(rows,[])
if __name__=="__main__":unittest.main()
