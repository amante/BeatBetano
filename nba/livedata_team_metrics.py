"""Research fallback for NBA Stats team metrics from final NBA LiveData boxscores."""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from nba_official_pace_capture import collect
from possession_intelligence import estimate_possessions
from prospective import utc
from team_identity import canonical

BASE = 'https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/boxscore'
SCHEDULE = BASE.split('/liveData/')[0] + '/staticData/scheduleLeagueV2_2.json'
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


def bind_history(schedule, history, cutoff, teams, prefix, games_per_team=4):
    def key(home, away, tip, home_points, away_points):
        return canonical(home), canonical(away), utc(tip), int(home_points), int(away_points)

    index = defaultdict(list)
    for day in schedule['leagueSchedule']['gameDates']:
        for game in day['games']:
            if game['gameStatus'] != 3 or not re.fullmatch(prefix + r'[0-9]{5}', game['gameId']):
                continue
            home, away = game['homeTeam'], game['awayTeam']
            identity = key(home['teamTricode'], away['teamTricode'], game['gameDateTimeUTC'],
                           home['score'], away['score'])
            index[identity].append(game['gameId'])
    counts = Counter()
    bindings, unresolved = {}, {}
    used = set()
    for game in sorted(history, key=lambda g: utc(g['tipoff_utc']), reverse=True):
        if utc(game['tipoff_utc']).astimezone(LEAGUE_TIME).date() > cutoff:
            continue
        sides = {canonical(game['home_team']), canonical(game['away_team'])}
        needed = {team for team in sides & teams if counts[team] < games_per_team}
        if not needed:
            continue
        gid = str(game['game_id'])
        identity = key(game['home_team'], game['away_team'], game['tipoff_utc'],
                       game['home_points'], game['away_points'])
        matches = index.get(identity, [])
        if len(matches) != 1 or matches[0] in used:
            unresolved[gid] = 'ambiguous_or_repeated' if matches else 'no_exact_match'
            continue
        bindings[gid] = matches[0]
        used.add(matches[0])
        counts.update(needed)
    return bindings, unresolved


def capture_fallback(game_ids, cutoff, directory, session=None):
    def fetch(game_id):
        url = f'{BASE}/boxscore_{game_id}.json'
        try:
            response = (session or requests).get(url, timeout=12)
            response.raise_for_status()
            game = summarize_game(response.json(), game_id, cutoff)
            raw = response.content
            (directory / f'boxscore_{game_id}.json').write_bytes(raw)
            game.update(source_url=url, source_sha256=hashlib.sha256(raw).hexdigest(),
                        observed_at_utc=datetime.now(timezone.utc).isoformat())
            return game, None
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            return None, {'game_id': game_id, 'error': type(exc).__name__, 'detail': str(exc)}

    with ThreadPoolExecutor(max_workers=24 if session is None else 1) as pool:
        observations = list(pool.map(fetch, game_ids))
    games = [game for game, _ in observations if game is not None]
    errors = [error for _, error in observations if error is not None]
    totals = defaultdict(lambda: {'games': 0, 'points': 0, 'allowed': 0, 'minutes': 0,
                                  'possessions_estimated': 0.0})
    for game in games:
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


def research_projection(snapshot, source, emitted_at):
    """Use the existing opponent adjustment and ML experiment at the later cutoff."""
    from possession_challenger import candidate
    from postmortem_engine import verify_seal
    from reproducible_slate import adjusted_ratings, digest

    verify_seal(snapshot)
    cutoff = utc(emitted_at)
    if utc(snapshot['created_at_utc']) > cutoff:
        raise ValueError('Research emission predates baseline')
    fallback = source['fallback']
    boxscores = {'games': []}
    pace = defaultdict(lambda: [0.0, 0])
    for observation in fallback['games']:
        observed = utc(observation['observed_at_utc'])
        if not utc(observation['tipoff_utc']) < observed <= cutoff:
            continue
        home, away = observation['teams']
        names = [canonical(team['team']) for team in (home, away)]
        stats = {name: {key: team[key] for key in ('points', 'possessions_estimated')}
                 for name, team in zip(names, (home, away))}
        game = {key: observation[key] for key in ('game_id', 'tipoff_utc')}
        game.update(home_team=names[0], away_team=names[1],
                    home_points=home['points'], away_points=away['points'])
        boxscores['games'].append({'game': game, 'observed_at_utc': observed.isoformat(),
                                  'team_statistics': stats})
        paired = (home['possessions_estimated'] + away['possessions_estimated']) / 2
        for name in names:
            pace[name][0] += paired
            pace[name][1] += observation['regulation_and_overtime_minutes']
    ratings = adjusted_ratings(boxscores, emitted_at)
    games = []
    for fixture in snapshot['predictions']:
        home, away = (canonical(fixture[side]) for side in ('home_team', 'away_team'))
        row = {'game_id': fixture['game_id'], 'home_team': home, 'away_team': away,
               'tipoff_utc': fixture['tipoff_utc'], 'base_home_ml': fixture['hybrid_p_home'],
               'candidate': None, 'home_plus20': None, 'away_plus20': None,
               'status': 'PASS_insufficient_opponent_sample'}
        if cutoff >= utc(fixture['tipoff_utc']):
            row['status'] = 'PASS_already_started'
        elif all(ratings.get(t, {}).get('status') == 'descriptive_schedule_adjusted' for t in (home, away)):
            possessions = sum(48 * pace[t][0] / pace[t][1] for t in (home, away)) / 2
            points = {t: possessions * (ratings[t]['opponent_adjusted_ortg'] +
                                        ratings[o]['opponent_adjusted_drtg']) / 200
                      for t, o in ((home, away), (away, home))}
            experiment = candidate(fixture['hybrid_p_home'], points[home], points[away])
            probability = experiment['experimental_p_home']
            row.update(status='research_team_ml', candidate=experiment,
                       projected_points=points, estimated_possessions=possessions,
                       home_ml=probability, away_ml=1-probability,
                       home_ml_delta_vs_hybrid=probability-fixture['hybrid_p_home'])
        games.append(row)
    report = {'baseline_snapshot_sha256': snapshot['content_sha256'],
              'team_metrics_sha256': digest(source), 'emitted_at_utc': emitted_at,
              'model_version': 'NBA_LIVEDATA_TEAM_ML_RESEARCH_V1', 'games': games,
              'ratings': ratings, 'production_approved': False, 'calibrated': False,
              'no_odds_input': True}
    return {**report, 'content_sha256': digest(report)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=date.fromisoformat, required=True)
    parser.add_argument('--game-id', action='append', default=[])
    parser.add_argument('--history', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    automatic = args.history is not None and args.snapshot is not None
    if (args.history is None) != (args.snapshot is None) or automatic == bool(args.game_id):
        parser.error('Provide game IDs or both --history and --snapshot')
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
            game_ids = args.game_id
            if automatic:
                try:
                    response = session.get(SCHEDULE, timeout=12)
                    response.raise_for_status()
                    schedule = response.json()
                    if schedule['leagueSchedule']['seasonYear'] != official['season']:
                        raise ValueError('Unexpected NBA schedule season')
                    snapshot = json.loads(args.snapshot.read_text())
                    teams = {canonical(g[side]) for g in snapshot['predictions']
                             for side in ('home_team', 'away_team')}
                    bindings, unresolved = bind_history(schedule, json.loads(args.history.read_text()),
                                                         cutoff, teams, prefix)
                    game_ids = list(bindings.values())
                    (args.output_dir / 'schedule.json').write_bytes(response.content)
                    result['crosswalk'] = {'bindings': bindings, 'unresolved': unresolved,
                                           'source_url': SCHEDULE,
                                           'source_sha256': hashlib.sha256(response.content).hexdigest(),
                                           'target_teams': sorted(teams)}
                except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
                    result['crosswalk'] = {'error': type(exc).__name__, 'detail': str(exc)}
            result['fallback'] = capture_fallback(game_ids, cutoff, args.output_dir)
            if automatic and 'target_teams' in result['crosswalk']:
                covered = {canonical(team['team']) for team in result['fallback']['teams']}
                result['crosswalk']['covered_teams'] = sorted(covered & teams)
                result['crosswalk']['missing_teams'] = sorted(teams - covered)
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
