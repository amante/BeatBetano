"""Compare explicit rotation scenarios using the shared NBA minute allocator."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from postmortem_engine import save_new, verify_seal
from prospective import utc
from reproducible_slate import digest
from rotation_allocation_adapter import allocate


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
    args = parser.parse_args()
    report = build(json.loads(args.coverage.read_text()), json.loads(args.snapshot.read_text()),
                   args.game_id, datetime.now(timezone.utc).isoformat())
    save_new(args.output, report)
    print(json.dumps({t: {'reported_out': len(r['reported_out_ids']),
                         'redistributed_minutes': round(sum(max(0, p['minute_delta'])
                                                            for p in r['minute_changes']), 2),
                         'assumed_eligible': len(r['assumed_eligible_ids']),
                         'uncovered_changed_minutes': r['uncovered_changed_minutes']}
                      for t, r in report['teams'].items()}))


if __name__ == '__main__':
    main()
