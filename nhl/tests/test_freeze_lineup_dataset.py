import json,tempfile,unittest,gzip
from pathlib import Path
from nhl.freeze_lineup_dataset import freeze
class FreezeTests(unittest.TestCase):
 def test_blocked_inputs_preserved_and_run_immutable(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);out=root/'saved/run-1.json'
   data={'report.json':dict(data_kind='source_readiness_only',games=[dict(game_id='1',home='BOS',away='MTL',start_utc='2099-11-03T00:00:00Z')]),'lineup_features.json':dict(kind='nhl_lineup_feature_packet_v1',games=[dict(game_id='1',teams=dict(BOS=dict(status='blocked'),MTL=dict(status='blocked')))])}
   for n in ['report.json','lineup_features.json','skater_history.json','prior_lineup_reference.json','lineup_changes.json']:(root/n).write_text(json.dumps(data.get(n,{})))
   for n in ['skater_history.sources.json.gz','prior_lineup_reference.sources.json.gz']:(root/n).write_bytes(gzip.compress(b'{}'))
   x=freeze(root,out,'1');self.assertFalse(x['records'][0]['complete_observed_inputs']);self.assertEqual(len(x['source_sha256']),7)
   with self.assertRaises(FileExistsError):freeze(root,out,'1')
 def test_bad_run_id_rejected(self):
  with self.assertRaises(ValueError):freeze('.','/tmp/unused','../x')
