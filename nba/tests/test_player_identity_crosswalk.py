import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from player_identity_crosswalk import build
from reproducible_slate import digest


class PlayerIdentityTests(unittest.TestCase):
    def test_conflicting_provider_ids_are_excluded_across_games(self):
        observed = '2026-11-09T10:00:00Z'
        snapshot = {'predictions': [{'game_id': 'target', 'tipoff_utc': '2026-11-09T23:00:00Z'}]}
        snapshot['content_sha256'] = digest(snapshot)
        seal = snapshot['content_sha256']

        def save(root, name, value):
            raw = json.dumps(value).encode()
            (root / name).write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()

        with tempfile.TemporaryDirectory() as tmp, patch('player_identity_crosswalk.datetime') as clock:
            root = Path(tmp)
            clock.now.return_value = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
            historical = [{'game_id': str(i), 'team': 'GS', 'player': 'Jose Smith',
                           'player_id': str(i), 'observed_at_utc': observed} for i in (1, 2)]
            availability = {'snapshot_sha256': seal, 'games': {'target': {'teams': {
                'GS': {'observed_at_utc': observed, 'players': [{'player_id': '1'}]}}}}}
            manifest = {'player_history.json': save(root, 'player_history.json', {'players': historical}),
                        'availability.json': save(root, 'availability.json', availability)}
            save(root, 'manifest.json', {'files': manifest})
            box = {'game': {'homeTeam': {'teamTricode': 'GSW', 'players': [
                {'name': 'José Smith', 'personId': 99}]},
                'awayTeam': {'teamTricode': 'DEN', 'players': []}}}
            games = [{'game_id': f'nba{i}', 'observed_at_utc': observed,
                      'source_sha256': save(root, f'boxscore_nba{i}.json', box)} for i in (1, 2)]
            metrics = {'baseline_snapshot_sha256': seal, 'fallback': {'games': games},
                       'crosswalk': {'bindings': {'1': 'nba1', '2': 'nba2'}}}
            report = build(snapshot, metrics, root, root)
            self.assertEqual(report['ambiguous_espn_ids'], ['1', '2'])
            self.assertEqual(report['fixtures'][0]['unresolved_espn_ids'], ['1'])
            del metrics['crosswalk']['bindings']['2']
            self.assertEqual(build(snapshot, metrics, root, root)['fixtures'][0]['player_ids'], {'1': '99'})
