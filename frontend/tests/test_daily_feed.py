import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collect_daily import parse_event
from merge_daily_history import merge
class DailyFeedTests(unittest.TestCase):
 def test_soccer_grouping_and_score(self):
  e={"id":"100","date":"2026-10-27T21:00Z","competitions":[{"status":{"type":{"name":"STATUS_FINAL","completed":True}},"competitors":[{"homeAway":"home","team":{"displayName":"Local"},"score":"2"},{"homeAway":"away","team":{"displayName":"Visitante"},"score":"1"}]}]}
  a=parse_event(e,"soccer","Chile","Primera División")
  self.assertEqual((a["country"],a["league"],a["home_score"]),("Chile","Primera División","2"))
 def test_tennis_competitors_no_home_away(self):
  e={"id":"20","date":"2026-10-27T14:00Z","competitions":[{"competitors":[{"athlete":{"displayName":"Jugador A"}},{"athlete":{"displayName":"Jugador B"}}]}]}
  x=parse_event(e,"tennis",None,"ATP")
  self.assertEqual(x["home"],"Jugador A")
 def test_archive_preserves_completed_result(self):
  old=[{"id":"1","sport":"nhl","start_utc":"2026-10-26T21:00Z","completed":True,"home_score":"3"}]
  new=[{"id":"1","sport":"nhl","start_utc":"2026-10-26T21:00Z","completed":False,"home_score":None}]
  self.assertEqual(merge(old,new)[0]["home_score"],"3")
if __name__=="__main__":unittest.main()
