"""Publish dated NBA rotation research from the normal daily capture artifacts."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from conditional_rotation_path import build_slate as paths
from livedata_team_metrics import LEAGUE_TIME
from team_identity import canonical
from player_possession_coverage import build as player_coverage
from postmortem_engine import save_new, verify_seal
from prospective import utc
from replacement_minute_scenarios import build_slate as rotations
from reproducible_slate import digest


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def process(path, archive_override=None):
    snapshot = read(path)
    verify_seal(snapshot)
    available = path.with_suffix('.availability')
    metrics = path.with_suffix('.team-metrics')
    requested = [g for g in snapshot['predictions'] if utc(now()) < utc(g['tipoff_utc'])]
    if not requested:
        return None
    try:
        crosswalk = read(metrics / 'player_crosswalk.json')
        manifest = read(available / 'manifest.json')['files']
        if crosswalk['availability_files'] != manifest:
            raise ValueError('Availability manifest differs from crosswalk')

        def observed(name):
            raw = (available / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest[name]:
                raise ValueError('Availability file digest mismatch: ' + name)
            return json.loads(raw)

        availability = observed('availability.json')
        rotation = observed('rotation.json')
        team_ml = read(metrics / 'team_ml_research.json')
        data = read(metrics / 'team_metrics.json')
        if archive_override is None:
            target = path.with_suffix('.possessions')
            binding = data['crosswalk']
            ids = list(binding['bindings'].values())
            schedule_bytes = (metrics / 'schedule.json').read_bytes()
            if hashlib.sha256(schedule_bytes).hexdigest() != binding['source_sha256']:
                raise ValueError('NBA schedule digest mismatch')
            schedule = json.loads(schedule_bytes)['leagueSchedule']
            prefix = '002' + schedule['seasonYear'][2:4]
            cutoff = date.fromisoformat(data['cutoff_date'])
            targets = set(binding['target_teams'])
            completed = [g for day in schedule['gameDates'] for g in day['games']
                         if g['gameStatus'] == 3 and g['gameId'].startswith(prefix)
                         and utc(g['gameDateTimeUTC']).astimezone(LEAGUE_TIME).date() <= cutoff]
            completed.sort(key=lambda g: (
                not any(canonical(g[side]['teamTricode']) in targets for side in ('homeTeam', 'awayTeam')),
                -utc(g['gameDateTimeUTC']).timestamp()))
            ids = list(dict.fromkeys(ids + [g['gameId'] for g in completed]))[:140]
            if not ids:
                raise ValueError('No historical NBA IDs available')
            command = [sys.executable, str(Path(__file__).with_name('capture_possessions.py')),
                       '--output-dir', str(target), '--budget-seconds', '65']
            for gid in ids:
                command.extend(['--game-id', gid])
            subprocess.run(command, check=True, timeout=105)
            archive_path = target / 'possessions.json'
            directories = [target, metrics]
        else:
            archive_path, directories = archive_override
        archive = read(archive_path)
        coverage = player_coverage(snapshot, crosswalk, availability, archive, now(), rotation)
        slate = rotations(coverage, snapshot, now(), archive, directories, data['fallback']['games'], team_ml)
        report = paths(snapshot, slate, coverage, team_ml, archive, now())
        for name, artifact in (('player-coverage', coverage), ('minute-slate', slate), ('rotation-path', report)):
            save_new(path.with_suffix(f'.{name}.json'), artifact)
        return report['games']
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(f'{path.name}: {type(exc).__name__}: {exc}', file=sys.stderr)
        return [{'game_id': str(g['game_id']), 'home_team': g['home_team'], 'away_team': g['away_team'],
                 'tipoff_utc': g['tipoff_utc'], 'status': 'PASS', 'comparison': None,
                 'blocked': {'source': ['rotation_inputs_unavailable']}} for g in requested]


def main():
    parser = argparse.ArgumentParser()
    for name in ('workdir', 'archive', 'latest'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--possession-archive', type=Path)
    parser.add_argument('--boxscore-dir', type=Path, action='append', default=[])
    args = parser.parse_args()
    override = None
    if args.possession_archive:
        if not args.boxscore_dir:
            parser.error('--possession-archive requires --boxscore-dir')
        override = (args.possession_archive, args.boxscore_dir)
    games = {}
    for path in sorted(args.workdir.glob('nba-*.json')):
        if '.' in path.stem:
            continue
        for row in process(path, override) or []:
            games[row['game_id']] = row
    if not games:
        print('No pregame NBA slate available')
        return
    emitted = now()
    for row in games.values():
        if row['comparison'] is not None and utc(emitted) >= utc(row['tipoff_utc']):
            for key in ('comparison', 'content_sha256', 'rotation_rating_deltas'):
                row.pop(key, None)
            row.update(status='PASS', comparison=None, blocked={'fixture': ['already_started']})
    report = {'model_version': 'NBA_CONDITIONAL_ROTATION_PATH_V1', 'emitted_at_utc': emitted,
              'fixtures': len(games), 'research_scenarios': sum(g['comparison'] is not None for g in games.values()),
              'games': list(games.values()), 'calibrated': False, 'production_approved': False}
    report['content_sha256'] = digest(report)
    save_new(args.archive / (report['content_sha256'] + '.json'), report)
    temporary = args.latest.with_suffix('.tmp')
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False))
    temporary.replace(args.latest)
    print(json.dumps({k: report[k] for k in ('fixtures', 'research_scenarios')}))


if __name__ == '__main__':
    main()
