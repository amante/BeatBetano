"""Audit immutable source captures without manufacturing model-ready features."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prospective import utc
from postmortem_engine import verify_seal
from verifiable_capture import score_path, resolve_official, save_new, pdf_table_pages
from official_injury_table import extract


def audit(source):
    source = Path(source).resolve()
    manifest = json.loads((source/'manifest.json').read_text())
    files = manifest['files']
    required = {'fixture_cohort.json', 'rosters.json', 'lineups.json',
                'historical_boxscores.json'}
    if not required <= set(files):
        raise ValueError('Capture manifest misses required inputs')
    for name, sha in files.items():
        path = (source/name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(source) or path == source:
            raise ValueError('Unsafe manifest path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Source digest mismatch: '+name)

    def load(name):
        if name not in files:
            raise ValueError('Unmanifested input: '+name)
        return json.loads((source/name).read_text())

    cohort, rosters, lineups = map(load, ('fixture_cohort.json', 'rosters.json', 'lineups.json'))
    verify_seal(cohort)
    for document in (rosters, lineups):
        if document.get('snapshot_sha256') != cohort['content_sha256']:
            raise ValueError('Source fixture cohort mismatch')
    fixtures = cohort['predictions']
    ids = [str(g['game_id']) for g in fixtures]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate fixtures')
    official = load('official_injury.json') if 'official_injury.json' in files else None
    if official:
        if 'official_injury.pdf' not in files or files['official_injury.pdf'] != official['pdf_sha256']:
            raise ValueError('Official PDF is not bound to manifest')
        parsed_rows = extract(pdf_table_pages((source/'official_injury.pdf').read_bytes()), continuous_table=True)
        resolution = resolve_official(parsed_rows, rosters, fixtures,
                                     official['published_at_utc'], official['observed_at_utc'])
    else:
        resolution = {'teams': [], 'unmatched_claims': []}
    claims = {(r['game_id'], r['team']): r for r in resolution['teams']}
    history = load('historical_boxscores.json')['games']
    history_ids = [str(r['game']['game_id']) for r in history]
    if len(set(history_ids)) != len(history_ids):
        raise ValueError('Duplicate historical fixtures')
    paths, gaps = [], []
    for row in history:
        gid = str(row['game']['game_id'])
        name = 'sports_summaries/'+gid+'.json'
        payload = load(name)
        if files[name] != row['sports_payload_sha256']:
            raise ValueError('Historical payload binding mismatch')
        try:
            paths.append({'game_id':gid, **score_path(payload, row['game'])})
        except (ValueError, KeyError, TypeError) as exc:
            gaps.append({'game_id':gid, 'reason':str(exc)})
    teams = []
    for g in fixtures:
        gid = str(g['game_id'])
        tip = utc(g['tipoff_utc'])
        for team in (g['home_team'], g['away_team']):
            roster = rosters.get('games', {}).get(gid, {}).get('teams', {}).get(team, {})
            players = roster.get('players', [])
            player_ids = [p['player_id'] for p in players]
            if len(set(player_ids)) != len(player_ids):
                raise ValueError('Duplicate roster identity')
            lineup = lineups.get('games', {}).get(gid, {}).get('teams', {}).get(team, {})
            matched = claims.get((gid, team), {}).get('official_claims', [])
            known = {p['player_id'] for p in matched}
            prior = [r for r in history if utc(r['game']['tipoff_utc']) < tip
                     and utc(r['observed_at_utc']) < tip]
            minute_ids = {p['player_id'] for r in prior for p in r['players']
                          if p['team'] == team and not p['did_not_play']
                          and p.get('minutes_played') is not None}
            roster_pregame = bool(roster.get('observed_at_utc')) and utc(roster['observed_at_utc']) < tip
            lineup_pregame = bool(lineup.get('observed_at_utc')) and utc(lineup['observed_at_utc']) < tip
            blockers = ['complete_active_status', 'adjusted_player_on_off',
                        'replacement_roles_and_quality', 'projected_minutes_and_usage',
                        'normalized_possessions', 'independent_holdout_validation']
            if not players or roster.get('roster_complete') is not True or not roster_pregame:
                blockers.append('complete_pregame_roster')
            # A provider confirmation is still not a verified ID-bound starting five.
            blockers.append('verified_starting_five_ids')
            teams.append({'game_id':gid, 'team':team, 'tipoff_utc':g['tipoff_utc'],
                          'roster_members':len(players), 'roster_observed_pregame':roster_pregame,
                          'official_status_claims':len(known),
                          'unknown_status_players':len(set(player_ids)-known),
                          'players_with_observed_minutes':len(set(player_ids)&minute_ids),
                          'lineup_status':lineup.get('lineup_status', 'missing'),
                          'lineup_observed_pregame':lineup_pregame,
                          'blocking_requirements':blockers, 'recommendation':'PASS'})
    return {'schema_version':1, 'created_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
            'fixture_cohort_sha256':cohort['content_sha256'],
            'games':len(fixtures), 'teams':teams,
            'historical_games':len(history), 'reconciled_score_paths':paths,
            'score_path_gaps':gaps,
            'gap_counts':dict(Counter(g['reason'] for g in gaps)),
            'unmatched_official_claims':resolution['unmatched_claims'],
            'official_rows_reparsed':len(parsed_rows) if official else 0,
            'normalized_possessions_available':False,
            'model_ready_games':0, 'production_approved':False,
            'recommendation':'PASS', 'no_odds_input':True,
            'note':'Historical minutes are observations, not projections. Unlisted injury statuses remain unknown. Source hashes establish integrity, not truth or independent validation.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.capture)
    path = Path(args.output)
    save_new(path.parent, path.name, report)
    print(json.dumps({k:report[k] for k in ('games','historical_games','model_ready_games','gap_counts')}))


if __name__ == '__main__':
    main()
