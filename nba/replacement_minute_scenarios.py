"""Compare explicit rotation scenarios using the shared NBA minute allocator."""
import argparse
import hashlib
import re
from collections import defaultdict
import json
from datetime import datetime, timezone
from pathlib import Path

from postmortem_engine import save_new, verify_seal
from prospective import utc
from reproducible_slate import digest
from rotation_allocation_adapter import allocate
from team_identity import canonical


def historical_usage(archive, directories, cutoff, teams):
    totals = defaultdict(lambda: [0.0, 0.0, 0])
    seen = set()
    for game in archive['games']:
        gid = game['game_id']
        if gid in seen:
            raise ValueError('Duplicate historical game')
        seen.add(gid)
        if not utc(game['completed_at_utc']) < utc(cutoff) or utc(game['evidence']['observed_at_utc']) > utc(cutoff):
            continue
        name = f'boxscore_{gid}.json'
        path = next((d / name for d in directories if (d / name).is_file()), None)
        if path is None:
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != game['boxscore_source']['sha256']:
            raise ValueError('Boxscore digest mismatch: ' + gid)
        box = json.loads(raw)['game']
        if box['gameId'] != gid or box['gameStatus'] != 3:
            raise ValueError('Expected matching final boxscore')
        for side in ('homeTeam', 'awayTeam'):
            team = box[side]
            code = canonical(team['teamTricode'])
            if code not in teams:
                continue
            for player in team['players']:
                stats = player.get('statistics', {})
                match = re.fullmatch(r'PT(?:(\d+)M)?(\d+(?:\.\d+)?)S', stats.get('minutes', ''))
                counts = [stats.get(key) for key in ('fieldGoalsAttempted', 'freeThrowsAttempted', 'turnovers')]
                if not match or any(type(n) is not int or n < 0 for n in counts):
                    continue
                minutes = int(match[1] or 0) + float(match[2]) / 60
                if minutes <= 0:
                    continue
                total = totals[code, str(player['personId'])]
                total[0] += counts[0] + .44 * counts[1] + counts[2]
                total[1] += minutes
                total[2] += 1
    return totals


def apply_usage(report, archive, directories):
    if not directories:
        raise ValueError('At least one boxscore directory is required')
    totals = historical_usage(archive, directories, report['emitted_at_utc'], report['teams'])
    for team, scenario in report['teams'].items():
        missing = []
        changes = scenario['minute_changes']
        for row in changes:
            total, minutes, games = totals.get((team, row['nba_player_id']), (0, 0, 0))
            row['usage_sample_games'] = games
            if games < 3 or not minutes:
                if row['reference_minutes'] or row['scenario_minutes']:
                    missing.append(row['espn_player_id'])
                continue
            rate = total / minutes
            row['historical_opportunities_per_minute'] = rate
            row['reference_opportunities'] = rate * row['reference_minutes']
            row['scenario_opportunities'] = rate * row['scenario_minutes']
            row['opportunity_delta'] = row['scenario_opportunities'] - row['reference_opportunities']
        scenario['usage'] = {'method': 'historical_fga_plus_044_fta_plus_tov_per_minute',
                             'minimum_games': 3, 'missing_player_ids': missing,
                             'status': 'partial_sample' if missing else 'complete_sample' if changes else 'no_allocation'}
        supported = [row for row in changes if 'reference_opportunities' in row]
        for field in ('reference', 'scenario'):
            total = sum(row[field + '_opportunities'] for row in supported)
            if total > 0 and not missing:
                for row in supported:
                    row[field + '_opportunity_share'] = row[field + '_opportunities'] / total
    report['usage_archive_sha256'] = digest(archive)
    report['status'] = 'research_minutes_and_historical_usage'
    report['content_sha256'] = digest({k:v for k,v in report.items() if k != 'content_sha256'})


def build(coverage, snapshot, game_id, emitted_at):
    verify_seal(coverage)
    verify_seal(snapshot)
    if coverage['baseline_snapshot_sha256'] != snapshot['content_sha256']:
        raise ValueError('Coverage belongs to another baseline')
    fixture = next(g for g in snapshot['predictions'] if str(g['game_id']) == game_id)
    if not utc(coverage['emitted_at_utc']) <= utc(emitted_at) < utc(fixture['tipoff_utc']):
        raise ValueError('Scenario must follow its evidence and precede tipoff')
    teams = {}
    for team in (fixture['home_team'], fixture['away_team']):
        roster = [p for p in coverage['players'] if p['game_id'] == game_id and p['team'] == team]
        excluded = [p['espn_player_id'] for p in roster if p['historical_minutes_projection'] is None]
        candidates = [p for p in roster if p['historical_minutes_projection'] is not None]
        out = {p['espn_player_id'] for p in candidates if p['availability'] == 'out'}
        uncertain = {p['espn_player_id'] for p in candidates if p['availability'] in ('unknown', 'questionable')}

        def run(absent):
            return allocate('nba', 'minutes', [
                {'player_id': p['espn_player_id'],
                 'status': 'out' if p['espn_player_id'] in absent else 'available',
                 'expected_weight': p['historical_minutes_projection'], 'max_units': 48}
                for p in candidates])

        reference = run(set())
        conditional = run(out)
        changes = []
        if reference['allocations'] is not None and conditional['allocations'] is not None:
            for p in candidates:
                pid = p['espn_player_id']
                before = reference['allocations'][pid]
                after = conditional['allocations'][pid]
                changes.append({'espn_player_id': pid, 'nba_player_id': p['nba_player_id'],
                                'reported_availability': p['availability'], 'reference_minutes': before,
                                'scenario_minutes': after, 'minute_delta': round(after-before, 5),
                                'effect_supported': p['status'] == 'supported_research_effect'})
        teams[team] = {'reference': reference, 'reported_out_scenario': conditional,
                       'assumed_eligible_ids': sorted(uncertain), 'reported_out_ids': sorted(out),
                       'excluded_missing_minute_sample': sorted(excluded),
                       'minute_changes': changes,
                       'uncovered_changed_minutes': round(sum(abs(p['minute_delta']) for p in changes
                                                             if not p['effect_supported']), 5)}
    report = {'game_id': game_id, 'emitted_at_utc': emitted_at, 'teams': teams,
              'baseline_snapshot_sha256': snapshot['content_sha256'],
              'coverage_sha256': coverage['content_sha256'],
              'method': 'proportional_historical_minutes_with_48_minute_cap',
              'status': 'research_minutes_only',
              'unresolved_inputs': ['replacement role and usage', 'complete two-sided player effects'],
              'home_ml': None, 'away_ml': None, 'home_plus20': None, 'away_plus20': None}
    return {**report, 'content_sha256': digest(report)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-id', required=True)
    for arg in ('coverage', 'snapshot', 'output'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--possessions', type=Path)
    parser.add_argument('--boxscore-dir', type=Path, action='append', default=[])
    args = parser.parse_args()
    if bool(args.possessions) != bool(args.boxscore_dir):
        parser.error('Supply --possessions and at least one --boxscore-dir together')
    coverage = json.loads(args.coverage.read_text())
    report = build(coverage, json.loads(args.snapshot.read_text()),
                   args.game_id, datetime.now(timezone.utc).isoformat())
    if args.possessions:
        archive = json.loads(args.possessions.read_text())
        if digest(archive) != coverage['effects']['input_sha256']:
            raise ValueError('Usage archive differs from the player effect sample')
        apply_usage(report, archive, args.boxscore_dir)
    save_new(args.output, report)
    print(json.dumps({t: {'reported_out': len(r['reported_out_ids']),
                         'redistributed_minutes': round(sum(max(0, p['minute_delta'])
                                                            for p in r['minute_changes']), 2),
                         'assumed_eligible': len(r['assumed_eligible_ids']),
                         'uncovered_changed_minutes': r['uncovered_changed_minutes']}
                      for t, r in report['teams'].items()}))


if __name__ == '__main__':
    main()
