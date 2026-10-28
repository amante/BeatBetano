import sys,unittest,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from consolidate_historical_games import consolidate
class TestConsolidation(unittest.TestCase):
 def test_merge_and_next_missing(self):
  with tempfile.TemporaryDirectory() as root:
   base=Path(root);a=base/"a";b=base/"b";a.mkdir();b.mkdir()
   rows=[{"id":str(i),"date":"2025-10-01","home":"BOS","away":"MTL"} for i in range(3)]
   for directory,i in ((a,0),(b,1)):
    (directory/(str(i)+".json")).write_text(json.dumps({"game_id":str(i),"date":"2025-10-01","home":"BOS","away":"MTL","goal_events_available":True,"boxscore":{"player_by_game_stats":{"homeTeam":{}}}}))
   summary,missing=consolidate(rows,[a,b],base/"out")
   self.assertEqual(summary["consolidated_games"],2)
   self.assertEqual([x["id"] for x in missing],["2"])
 def test_conflicting_records_fail_closed(self):
  with tempfile.TemporaryDirectory() as root:
   base=Path(root);a=base/"a";b=base/"b";a.mkdir();b.mkdir()
   rec={"game_id":"1","date":"2025-10-01","home":"BOS","away":"MTL","goal_events_available":True,"boxscore":{"player_by_game_stats":{"homeTeam":{}}}}
   (a/"1.json").write_text(json.dumps(rec))
   (b/"1.json").write_text(json.dumps(dict(rec,pbp_event_count=10)))
   with self.assertRaises(ValueError):
    consolidate([{"id":"1","date":"2025-10-01","home":"BOS","away":"MTL"}],[a,b],base/"out")
if __name__=="__main__":unittest.main()
