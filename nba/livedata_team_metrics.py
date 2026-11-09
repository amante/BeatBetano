"""Research fallback for NBA Stats team metrics from final NBA LiveData boxscores."""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from nba_official_pace_capture import collect
from possession_intelligence import estimate_possessions
from prospective import utc

BASE = 'https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/boxscore'
LEAGUE_TIME = ZoneInfo('America/New_York')


def summarize_game(payload, game_id, cutoff):
    game = payload['game']
    if game['gameId'] != game_id or game['gameStatus'] != 3:
        raise ValueError('Expected matching final boxscore')
    if utc(game['gameTimeUTC']).astimezone(LEAGUE_TIME).date() > cutoff:
        raise ValueError('Game falls after requested cutoff')
    period = game['period']
    if type(period) is not int or period < 4 or game['regulationPeriods'] != 4:
        raise ValueError('Invalid game duration')
    rows = []
    for side in ('homeTeam', 'awayTeam'):
        team = game[side]
        stats = team['statistics']
        fields = [stats[k] for k in ('fieldGoalsAttempted', 'freeThrowsAttempted',
                                    'reboundsOffensive', 'turnoversTotal', 'points')]
        if any(type(value) is not int or value < 0 for value in fields) or fields[-1] != team['score']:
            raise ValueError('Invalid or unreconciled team totals')
        possessions = estimate_possessions(*fields[:4])
        if not 50 <= possessions <= 180:
            raise ValueError('Implausible possession estimate')
        rows.append({'team_id': team['teamId'], 'team': team['teamTricode'],
                     'points': fields[-1], 'possessions_estimated': possessions})
    if rows[0]['team_id'] == rows[1]['team_id'] or rows[0]['points'] == rows[1]['points']:
        raise ValueError('Invalid final matchup')
    return {'game_id': game_id, 'tipoff_utc': game['gameTimeUTC'],
            'regulation_and_overtime_minutes': 48 + 5 * (period - 4), 'teams': rows}


def capture_fallback(game_ids, cutoff, directory, session):
    games, errors = [], []
    totals = defaultdict(lambda: {'games': 0, 'points': 0, 'allowed': 0, 'minutes': 0,
                                  'possessions_estimated': 0.0})
    for game_id in game_ids:
        url = f'{BASE}/boxscore_{game_id}.json'
        try:
            response = session.get(url, timeout=12)
            response.raise_for_status()
            game = summarize_game(response.json(), game_id, cutoff)
            raw = response.content
            (directory / f'boxscore_{game_id}.json').write_bytes(raw)
            game.update(source_url=url, source_sha256=hashlib.sha256(raw).hexdigest(),
                        observed_at_utc=datetime.now(timezone.utc).isoformat())
            games.append(game)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            errors.append({'game_id': game_id, 'error': type(exc).__name__, 'detail': str(exc)})
            continue
        home, away = game['teams']
        paired = (home['possessions_estimated'] + away['possessions_estimated']) / 2
        for team, opponent in ((home, away), (away, home)):
            total = totals[team['team_id']]
            total['team'] = team['team']
            total['games'] += 1
            total['points'] += team['points']
            total['allowed'] += opponent['points']
            total['possessions_estimated'] += paired
            total['minutes'] += game['regulation_and_overtime_minutes']
    teams = []
    for team_id, total in sorted(totals.items()):
        possessions = total['possessions_estimated']
        teams.append({'team_id': team_id, **total, 'pace_estimated': 48 * possessions / total['minutes'],
                      'off_rating_estimated': 100 * total['points'] / possessions,
                      'def_rating_estimated': 100 * total['allowed'] / possessions})
    return {'method': 'paired_average_fga_plus_044_fta_minus_oreb_plus_total_turnovers',
            'games': games, 'teams': teams, 'errors': errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=date.fromisoformat, required=True)
    parser.add_argument('--game-id', action='append', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    season_start = args.date.year if args.date.month >= 10 else args.date.year - 1
    prefix = f'002{season_start % 100:02d}'
    if len(args.game_id) != len(set(args.game_id)) or any(
            not re.fullmatch(prefix + r'[0-9]{5}', game_id) for game_id in args.game_id):
        parser.error('Supply distinct regular-season NBA game IDs for the requested season')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with requests.Session() as session:
        official = collect(args.date.isoformat(), session=session)
        cutoff = date.fromisoformat(official['cutoff_date'])
        official_ids = {row['TEAM_ID'] for row in official['teams']}
        complete = len(official_ids) == len(official['teams']) == 30
        result = {'official': official, 'cutoff_date': cutoff.isoformat(),
                  'selected_source': 'nba_stats' if complete else 'nba_livedata_estimated',
                  'forecast_adjustment_applied': False}
        if not complete:
            result['fallback'] = capture_fallback(args.game_id, cutoff, args.output_dir, session)
            if not result['fallback']['teams']:
                result['selected_source'] = 'unavailable'
    with (args.output_dir / 'team_metrics.json').open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
    fallback = result.get('fallback', {})
    print(json.dumps({'source': result['selected_source'], 'official_teams': len(official_ids),
                      'fallback_games': len(fallback.get('games', [])),
                      'fallback_teams': len(fallback.get('teams', [])),
                      'fallback_errors': len(fallback.get('errors', []))}))
    if result['selected_source'] == 'unavailable':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
