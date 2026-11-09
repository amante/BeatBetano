"""Measure pregame roster coverage of the existing NBA possession effect model."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from player_possession_effects import fit
from postmortem_engine import provenance, save_new, verify_seal
from prospective import utc
from reproducible_slate import digest
from team_identity import canonical


def build(snapshot, crosswalk, availability, archive, emitted_at, rotation=None):
    verify_seal(snapshot)
    verify_seal(crosswalk)
    seal = snapshot['content_sha256']
    if crosswalk['baseline_snapshot_sha256'] != seal or availability['snapshot_sha256'] != seal:
        raise ValueError('Player evidence belongs to another baseline')
    if rotation is not None and rotation['snapshot_sha256'] != seal:
        raise ValueError('Rotation belongs to another baseline')
    cutoff = utc(emitted_at)
    if not utc(snapshot['created_at_utc']) <= utc(crosswalk['observed_at_utc']) <= cutoff:
        raise ValueError('Invalid crosswalk observation time')
    if rotation is not None and utc(rotation['observed_at_utc']) > cutoff:
        raise ValueError('Rotation was observed after the report cutoff')
    fixtures = {str(g['game_id']): g for g in snapshot['predictions'] if cutoff < utc(g['tipoff_utc'])}
    if not fixtures:
        raise ValueError('No remaining pregame fixtures')
    tip = min((g['tipoff_utc'] for g in fixtures.values()), key=utc)
    provenance(archive['evidence'], cutoff, utc(tip), 'possession archive')
    effects = fit(archive, emitted_at, tip)
    rows = []
    for binding in crosswalk['fixtures']:
        gid, team = str(binding['game_id']), binding['team']
        if gid not in fixtures:
            continue
        fixture = fixtures[gid]
        if canonical(team) not in {canonical(fixture['home_team']), canonical(fixture['away_team'])}:
            raise ValueError('Crosswalk fixture team mismatch')
        source = availability['games'][gid]['teams'][team]
        if not utc(source['observed_at_utc']) <= cutoff:
            raise ValueError('Roster was observed after the report cutoff')
        rotation_team = (rotation or {}).get('games', {}).get(gid, {}).get('teams', {}).get(team, {})
        minutes = {row['player_id']: row['minutes_projection']
                   for row in rotation_team.get('provisional_rotation', [])}
        for player in source['players']:
            espn_id = player['player_id']
            nba_id = binding['player_ids'].get(espn_id)
            if nba_id and crosswalk['links'][espn_id]['nba_player_id'] != nba_id:
                raise ValueError('Crosswalk player binding mismatch')
            effect = effects['players'].get(nba_id, {})
            supported = (effect.get('status') == 'research_effects_only'
                         and canonical(team) in {canonical(t) for t in effect['historical_teams']})
            role = ('provider_starter' if player['starter_projected'] else
                    'historical_rotation' if minutes.get(espn_id) is not None else 'unknown')
            rows.append({'game_id': gid, 'team': team, 'espn_player_id': espn_id,
                         'nba_player_id': nba_id, 'role': role, 'availability': player['status'],
                         'historical_minutes_projection': minutes.get(espn_id),
                         'effect_sample_possessions': effect.get('effect_sample_possessions'),
                         'effect_sample_games': len(effect.get('game_ids', [])),
                         'status': 'supported_research_effect' if supported else
                                   'missing_player_link' if nba_id is None else 'insufficient_effect',
                         'offense_effect_per_100': effect['offense_effect_per_100'] if supported else None,
                         'defense_effect_per_100': effect['defense_effect_per_100'] if supported else None})
    coverage = {}
    for role in ('provider_starter', 'historical_rotation', 'unknown'):
        subset = [row for row in rows if row['role'] == role]
        coverage[role] = {'entries': len(subset),
                          'linked': sum(row['nba_player_id'] is not None for row in subset),
                          'supported': sum(row['status'] == 'supported_research_effect' for row in subset)}
    report = {'baseline_snapshot_sha256': seal, 'crosswalk_sha256': crosswalk['content_sha256'],
              'emitted_at_utc': emitted_at, 'effects': effects, 'players': rows,
              'coverage': coverage, 'games_in_training': len(archive['games']),
              'fixtures_observed': len(fixtures), 'production_approved': False}
    return {**report, 'content_sha256': digest(report)}


def main():
    parser = argparse.ArgumentParser()
    for arg in ('snapshot', 'crosswalk', 'availability-dir', 'possessions', 'output'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    crosswalk = json.loads(args.crosswalk.read_text())
    manifest = json.loads((args.availability_dir / 'manifest.json').read_text())['files']

    def verified(name):
        raw = (args.availability_dir / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[name]:
            raise ValueError('Availability digest mismatch: ' + name)
        return json.loads(raw)

    if manifest != crosswalk['availability_files']:
        raise ValueError('Availability manifest differs from player crosswalk')
    rotation = verified('rotation.json') if 'rotation.json' in manifest else None
    report = build(snapshot, crosswalk, verified('availability.json'),
                   json.loads(args.possessions.read_text()),
                   datetime.now(timezone.utc).isoformat(), rotation)
    save_new(args.output, report)
    print(json.dumps(report['coverage']))


if __name__ == '__main__':
    main()
