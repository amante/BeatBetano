import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sporting_feed import extract
from player_status_intake import reconcile
from active_roster_resolver import resolve
from capture_availability import capture
ROOT=Path(__file__).resolve().parents[2]
CAPTURE=ROOT/'reports/nba-availability-2026-11-04-2147'

def load(name):return json.loads((CAPTURE/(name+'.json')).read_text())

class AvailabilityCaptureTests(unittest.TestCase):
    def test_real_current_schema_covers_both_teams(self):
        p=json.loads((ROOT/'nba/tests/fixtures/espn_injury_group_shape.json').read_text())
        snap={'predictions':[{'game_id':'1','home_team':'WSH','away_team':'ATL'}]}
        s=extract(p,snap,'2026-11-04T21:46:00Z')['games']['1']['supplementary_injury_observations']
        self.assertEqual({r['team'] for r in s['items']},{'ATL','WSH'})
        self.assertGreater(len(s['items']),0)
        self.assertFalse(s['source_verified_official'])

    def test_new_observation_replays_without_rewriting_frozen_snapshot(self):
        snap=json.loads((ROOT/'reports/nba-2026-11-04/snapshot.json').read_text())
        for name,sha in load('manifest')['files'].items():
            self.assertEqual(hashlib.sha256((CAPTURE/name).read_bytes()).hexdigest(),sha)
        st=reconcile(snap,load('roster'),load('sporting'))
        self.assertEqual(st,load('status'))
        av=resolve(snap,load('roster'),st,load('lineups'))
        self.assertEqual(av,load('availability'))
        claims=sum(len(t) for g in st['games'].values() for t in g['teams'].values())
        self.assertEqual(claims,81)
        self.assertEqual(st['unmatched_claims'],[])
        self.assertEqual(st['conflicts'],[])
        teams=[t for g in av['games'].values() for t in g['teams'].values()]
        self.assertEqual(sum(len(t['players']) for t in teams),452)
        self.assertEqual(sum(p['status']=='unknown' for t in teams for p in t['players']),371)
        self.assertTrue(all(not t['allocation_ready'] for t in teams))
        self.assertGreater(load('summary')['captured_at_utc'],snap['created_at_utc'])

    def test_tampered_snapshot_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            capture({'content_sha256':'bad','predictions':[]},'/unused')

if __name__=='__main__':unittest.main()
