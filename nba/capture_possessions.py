"""Capture completed NBA LiveData and normalize it for the possession bridge."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import requests

from prospective import utc
from reproducible_slate import digest

BASE = 'https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData'


def normalize(game_id, directory, play_bytes, box_bytes, observed_at):
    from pbpstats.data_loader import LivePossessionFileLoader, LivePossessionLoader
    from pbpstats.resources.enhanced_pbp.turnover import Turnover

    play = json.loads(play_bytes)['game']
    box = json.loads(box_bytes)['game']
    if play['gameId'] != game_id or box['gameId'] != game_id or box['gameStatus'] != 3:
        raise ValueError('Source game identity or final status mismatch')
    end = play['actions'][-1]
    if (end['actionType'], end['subType']) != ('game', 'end'):
        raise ValueError('Missing final play-by-play action')
    completed = utc(re.sub(r'\.(\d+)Z$', lambda m: '.' + m[1].ljust(6, '0') + 'Z', end['timeActual']))
    if not utc(box['gameTimeUTC']) < completed < utc(observed_at):
        raise ValueError('Invalid completed game timestamps')
    teams = {box[side]['teamId']: box[side] for side in ('homeTeam', 'awayTeam')}
    if len(teams) != 2:
        raise ValueError('Expected two teams')
    home_id, away_id = teams
    score = {home_id: 0, away_id: 0}
    rosters = {t: {str(p['personId']) for p in data['players']} for t, data in teams.items()}
    if (any(len(rosters[t]) < 5 or len(rosters[t]) != len(teams[t]['players']) for t in teams)
            or rosters[home_id] & rosters[away_id]):
        raise ValueError('Invalid historical roster identities')
    normalized = []
    class LiveFeedLoader:
        file_directory = str(directory)
        def load_data(self, source_game_id):
            if source_game_id != game_id:
                raise ValueError('Unexpected parser game identity')
            # The 2026-27 feed omits personId on team and administrative events.
            # pbpstats expects 0 for an event with no player attribution.
            for action in play['actions']:
                if action['actionType'] in {'period', 'game', 'timeout', 'rebound', 'violation', 'turnover'} and action.get('personId') is None:
                    action['personId'] = 0
            return {'game': play}

    source = LivePossessionFileLoader(str(directory))
    source.enhanced_pbp_source_loader = LiveFeedLoader()
    loader = LivePossessionLoader(game_id, source)
    for possession in loader.items:
        start = next((event for event in possession.events
                      if event.action_type not in {'substitution', 'period', 'timeout', 'game'}), None)
        if start is None:
            continue
        offense = start.get_offense_team_id()
        if offense not in teams:
            raise ValueError('Missing possession offense')
        defense = away_id if offense == home_id else home_id
        last = possession.events[-1]
        current = {home_id: int(last.home_score), away_id: int(last.away_score)}
        points = current[offense] - score[offense]
        turnover = isinstance(last, Turnover) and not last.is_no_turnover
        if current[defense] != score[defense] or not 0 <= points <= 4 or (turnover and points):
            raise ValueError('Unrepresentable scoring within possession')
        lineups = {t: [str(p) for p in start.current_players[t]] for t in teams}
        if any(len(lineup) != 5 or len(set(lineup)) != 5 or not set(lineup) <= rosters[t]
               for t, lineup in lineups.items()):
            raise ValueError('Invalid possession-start quintet')
        normalized.append({'sequence': len(normalized), 'team': teams[offense]['teamTricode'],
                           'points': points, 'turnover': turnover,
                           'offense_lineup': lineups[offense], 'defense_lineup': lineups[defense]})
        score = current
    if score != {t: int(data['score']) for t, data in teams.items()}:
        raise ValueError('Possessions do not reconcile to final boxscore')
    evidence = {'verified': True, 'source_url': f'{BASE}/playbyplay/playbyplay_{game_id}.json',
                'source_sha256': hashlib.sha256(play_bytes).hexdigest(),
                'available_at_utc': observed_at, 'observed_at_utc': observed_at}
    return {'game_id': game_id, 'tipoff_utc': box['gameTimeUTC'],
            'completed_at_utc': completed.isoformat(),
            'duration_minutes': 48 + 5 * (int(box['period']) - 4),
            'home_team': teams[home_id]['teamTricode'], 'away_team': teams[away_id]['teamTricode'],
            'home_points': score[home_id], 'away_points': score[away_id],
            'team_rosters': {teams[t]['teamTricode']: sorted(ids) for t, ids in rosters.items()},
            'lineup_attribution': 'possession_start', 'complete': True, 'possessions': normalized,
            'evidence': evidence, 'lineup_evidence': evidence,
            'boxscore_source': {'url': f'{BASE}/boxscore/boxscore_{game_id}.json',
                                'sha256': hashlib.sha256(box_bytes).hexdigest()}}


def capture(game_ids, directory):
    from pbpstats.resources.enhanced_pbp.rebound import EventOrderError
    from pbpstats.resources.enhanced_pbp.start_of_period import InvalidNumberOfStartersException

    directory = Path(directory)
    if not game_ids or len(set(game_ids)) != len(game_ids) or any(
            not re.fullmatch(r'002[0-9]{7}', gid) for gid in game_ids):
        raise ValueError('Supply distinct NBA regular-season game IDs')
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'pbp').mkdir()
    games, rejected = [], []
    with requests.Session() as session:
        for gid in game_ids:
            try:
                play = session.get(f'{BASE}/playbyplay/playbyplay_{gid}.json', timeout=15)
                play.raise_for_status()
                box = session.get(f'{BASE}/boxscore/boxscore_{gid}.json', timeout=15)
                box.raise_for_status()
                observed = datetime.now(timezone.utc).isoformat()
                (directory / 'pbp' / f'live_{gid}.json').write_bytes(play.content)
                (directory / f'boxscore_{gid}.json').write_bytes(box.content)
                games.append(normalize(gid, directory, play.content, box.content, observed))
            except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, IndexError, EventOrderError, InvalidNumberOfStartersException) as exc:
                rejected.append({'game_id': gid, 'reason': f'{type(exc).__name__}: {exc}'})
    report = {'games': games, 'rejected': rejected, 'parser_version': version('pbpstats')}
    if games:
        latest = max(games, key=lambda g: utc(g['evidence']['observed_at_utc']))
        report['evidence'] = {**latest['evidence'], 'source_url': BASE,
                              'source_sha256': digest([(g['evidence'], g['boxscore_source']) for g in games])}
    with (directory / 'possessions.json').open('x') as output:
        json.dump(report, output, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-id', action='append', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    report = capture(args.game_id, args.output_dir)
    print(json.dumps({'games': len(report['games']), 'rejected': report['rejected']}))
    if not report['games']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
