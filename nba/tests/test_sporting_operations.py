import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sporting_archive import team_observation,player_ledger,bundles,actual_games
from forward_publication import build
from forward_ledger import load_observations
ROOT=Path(__file__).resolve().parents[2]
TIP='2026-11-05T02:00:00Z'
ASOF='2026-11-05T04:00:00Z'


def record(time='2026-11-05T01:00:00Z',status='unknown'):
    return {'ref':'sample','availability':{'games':{'g':{'teams':{'BOS':{
        'observed_at_utc':time,'roster_complete':True,'allocation_ready':False,
        'players':[{'player_id':'1','player':'Example','status':status,'status_sources':[]}]}}}}},
        'lineups':{'games':{'g':{'teams':{'BOS':{'observed_at_utc':time,'starters':['Example'], 'lineup_status':'projected'}}}}}}

class SportingOperationsTests(unittest.TestCase):
    def test_latest_before_tip_only_and_unknown_is_not_active(self):
        a=record();late=record('2026-11-05T03:00:00Z','out')
        selected=team_observation([a,late],'g','BOS',TIP,ASOF)
        self.assertEqual(selected['players'][0]['status'],'unknown')
        self.assertEqual(selected['lineup_status'],'projected')
        self.assertFalse(selected['allocation_ready'])
        self.assertIsNone(team_observation([late],'g','BOS',TIP,ASOF))

    def test_actual_minutes_are_postgame_targets_not_availability(self):
        actual={'game':{'game_id':'g','tipoff_utc':TIP},'observed_at_utc':'2026-11-05T03:00:00Z',
                'players':[{'team':'BOS','player_id':'1','player':'Example','minutes_played':None,'did_not_play':True}]}
        result=player_ledger([record()],[actual],ASOF)['rows'][0]
        self.assertEqual(result['pregame_status'],'unknown')
        self.assertIsNone(result['minutes_actual'])
        self.assertFalse(result['fit_for_availability_impact'])
        actual['observed_at_utc']='2026-11-05T01:00:00Z'
        with self.assertRaises(ValueError):player_ledger([record()],[actual],ASOF)

    def test_bad_sidecar_manifest_is_not_used(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'captures'/'one';path.mkdir(parents=True)
            (path/'availability.json').write_text('{}')
            (path/'manifest.json').write_text(json.dumps({'files':{'availability.json':'bad'}}))
            with patch('sporting_archive.LEGACY',Path(tmp)/'missing'):
                good,errors=bundles(tmp)
            self.assertEqual(good,[]);self.assertEqual(len(errors),1)

    def test_actual_target_hash_rejects_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'player-games';folder.mkdir()
            p=folder/'one.json';p.write_text('{}')
            p.with_suffix('.json.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(actual_games(tmp),[{}])
            p.write_text('{"changed": true}')
            with self.assertRaises(ValueError):actual_games(tmp)

    def test_real_publication_preserves_frozen_probabilities_and_coverage(self):
        protocol=json.loads((ROOT/'reports/nba-validation-2026-11-04/prospective_protocol.json').read_text())
        obs=load_observations(ROOT/'reports/nba-forward')
        records,errors=bundles(ROOT/'reports/nba-sporting')
        r=build(protocol,obs,records,ASOF,errors)
        self.assertEqual(len(r['games']),15)
        original=json.loads((ROOT/'reports/nba-2026-11-04/snapshot.json').read_text())
        byid={g['game_id']:g for g in r['games']}
        for p in original['predictions']:
            for key in ('elo_p_home','challenger_p_home'):
                self.assertEqual(byid[p['game_id']]['first_prediction'][key],p[key])
        self.assertIsNone(r['performance_metrics'])
        self.assertFalse(r['sporting_adjustment_applied'])
        self.assertFalse(r['calendar_date_coverage_chile']['2026-11-08'])
        self.assertEqual(errors,[])

if __name__=='__main__':unittest.main()
