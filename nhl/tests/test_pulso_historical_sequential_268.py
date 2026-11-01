import tempfile,unittest
from nhl.pulso_historical_sequential_268 import execute

class Seq268(unittest.TestCase):
 def test_sequential_batches_share_cache(self):
  labels=[];counts=[]
  for i in range(7):
   labels.append({"game_id":str(i+1),"date":f"2026-10-{i+1:02d}","home":"BOS","away":"MTL","ml_winner":"home"})
  def fetcher(gid):
   counts.append(gid)
   def side(pid):
    return {"goalies":[{"playerId":pid,"starter":True,"shotsAgainst":20,"saves":18}]}
   return {"id":int(gid),"gameDate":labels[int(gid)-1]["date"],
           "playerByGameStats":{"homeTeam":side(10),"awayTeam":side(20)}},{"url":"official","sha256":"a"*64}
  with tempfile.TemporaryDirectory() as d:
   r=execute(labels,d,batch_size=3,delay=0,fetcher=fetcher)
   self.assertEqual([b["attempted"] for b in r["batch_report"]["completed_batches"]],[3,3,1])
   self.assertEqual(r["batch_report"]["captured_games"],7)
   self.assertEqual(r["eligible_count"],2)
   r2=execute(labels,d,batch_size=3,delay=0,fetcher=fetcher)
   self.assertEqual(len(counts),7)
   self.assertEqual(r2["batch_report"]["completed_batches"][0]["status_counts"],{"cached":3})
 def test_invalid_batch_bounds(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):execute([{"game_id":"1"}],d,batch_size=0)
 def test_no_fake_coverage_after_failed_api(self):
  labels=[{"game_id":"1","date":"2026-10-01","home":"BOS","away":"MTL","ml_winner":"home"}]
  with tempfile.TemporaryDirectory() as d:
   r=execute(labels,d,fetcher=lambda _:(_ for _ in ()).throw(OSError("offline")),delay=0)
   self.assertFalse(r["batch_report"]["complete_source_coverage"])
   self.assertEqual(r["batch_report"]["captured_games"],0)
if __name__=="__main__":unittest.main()
