import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from edge_probe import run,markdown
class Reply:
 def __init__(self,status_code,payload=None):
  self.status_code=status_code
  self.headers={}
  self.payload=payload or {}
 def json(self):return self.payload
class Test(unittest.TestCase):
 def test_rate_limited(self):
  x=run(lambda url:Reply(429))
  self.assertFalse(x["usable"])
  self.assertIn("429",markdown(x))
 def test_valid_response(self):
  x=run(lambda url:Reply(200,{"data":[{"playerId":1}]}))
  self.assertTrue(x["usable"])
  self.assertIn("data",x["endpoint_results"][0]["top_level_keys"])
if __name__=="__main__":unittest.main()
