import sys,unittest,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backfill_all_history import backfill
class TestAutomatedBackfill(unittest.TestCase):
 def test_empty_ledger(self):
  with tempfile.TemporaryDirectory() as d:
   r=backfill([],Path(d),10,0)
   self.assertTrue(r["complete"])
   self.assertEqual(r["remaining"],0)
 def test_recognizes_existing_verified_cache_without_requests(self):
  row={"id":"123","date":"2024-10-01","home":"BOS","away":"MTL"}
  item={"game_id":"123","date":"2024-10-01","goal_events_available":True,
        "boxscore":{"player_by_game_stats":{"homeTeam":{}}}}
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/"123.json").write_text(json.dumps(item))
   r=backfill([row],Path(d),10,0)
   self.assertEqual(r["cached_validated"],1)
   self.assertEqual(r["newly_fetched"],0)
if __name__=="__main__":unittest.main()
