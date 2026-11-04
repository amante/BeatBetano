"""Replay the archived real slate without HTTP or postgame information."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prospective import generate
from reproducible_slate import build, markdown, digest

ROOT=Path(__file__).resolve().parents[2]/'reports'/'nba-2026-11-04'

def load(name):return json.loads((ROOT/(name+'.json')).read_text())

class Nov4ArchiveTests(unittest.TestCase):
    def test_manifest_and_frozen_baseline_replay(self):
        for name,expected in load('manifest')['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)
        snap=load('snapshot')
        self.assertEqual(digest({k:v for k,v in snap.items() if k!='content_sha256'}),snap['content_sha256'])
        replay=generate(load('history'),load('fixtures'),snap['created_at_utc'])
        # libm exp/pow can differ by one ULP between macOS and Linux.
        # Preserve original archive bytes/digest, compare probabilities at
        # 1e-12 absolute tolerance, and require every other field to be exact.
        for expected,actual in zip(snap['predictions'],replay['predictions']):
            for key in ('elo_p_home','challenger_p_home','hybrid_p_home'):
                self.assertAlmostEqual(actual[key],expected[key],delta=1e-12)
                actual[key]=expected[key]
        replay['content_sha256']=snap['content_sha256']
        self.assertEqual(replay,snap)
        self.assertEqual(len(snap['predictions']),13)
        self.assertEqual(load('history_audit')['cleaning']['coverage_verified'],True)
        self.assertEqual(len([g for g in load('history') if g['season']!=2027]),3690)

    def test_report_replays_all_fields_without_filling_missing_values(self):
        r=build(load('snapshot'),load('boxscores'),**{k:load(k) for k in ('roster','lineups','availability','minutes','scenarios')})
        self.assertEqual(r,load('report'))
        self.assertEqual(markdown(r),(ROOT/'report.md').read_text())
        self.assertEqual(sum(len(t['players']) for g in r['games'] for t in g['teams'].values()),452)
        self.assertEqual(r['games_count'],13)
        for g in r['games']:
            for team in g['teams'].values():
                self.assertIsNone(team['final_ml_probability'])
                self.assertIsNone(team['reach_plus20_probability'])
                self.assertIsNone(team['availability_adjusted_ortg'])
                self.assertTrue(all(p['projected_minutes'] is None for p in team['players']))

if __name__=='__main__':unittest.main()
