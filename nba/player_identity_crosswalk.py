"""Bind NBA and ESPN player IDs using paired final boxscores."""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone

from player_status_intake import normalize
from postmortem_engine import verify_seal
from prospective import utc
from reproducible_slate import digest
from team_identity import canonical


def build(snapshot, metrics, boxscore_dir, availability_dir):
    verify_seal(snapshot)
    if metrics.get('baseline_snapshot_sha256') != snapshot['content_sha256']:
        raise ValueError('Metrics belong to another snapshot')
    emitted = datetime.now(timezone.utc).isoformat()
    manifest = json.loads((availability_dir / 'manifest.json').read_text())['files']

    def read_verified(directory, name, sha):
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Source digest mismatch: ' + name)
        return json.loads(raw)

    sample = read_verified(availability_dir, 'player_history.json', manifest['player_history.json'])
    availability = read_verified(availability_dir, 'availability.json', manifest['availability.json'])
    if availability['snapshot_sha256'] != snapshot['content_sha256']:
        raise ValueError('Availability belongs to another snapshot')
    historical = defaultdict(list)
    for player in sample['players']:
        if utc(player['observed_at_utc']) <= utc(emitted):
            historical[str(player['game_id'])].append(player)
    nba_games = {g['game_id']: g for g in metrics['fallback']['games']}
    evidence = defaultdict(list)

    for espn_id, nba_id in metrics['crosswalk']['bindings'].items():
        game = nba_games.get(nba_id)
        if game is None or espn_id not in historical or utc(game['observed_at_utc']) > utc(emitted):
            continue
        box = read_verified(boxscore_dir, f'boxscore_{nba_id}.json', game['source_sha256'])['game']
        for side in ('homeTeam', 'awayTeam'):
            team = box[side]
            team_code = canonical(team['teamTricode'])
            nba_by_name = defaultdict(list)
            espn_by_name = defaultdict(list)
            for player in team['players']:
                name = player.get('name')
                if name and player.get('personId'):
                    nba_by_name[normalize(name)].append(str(player['personId']))
            for player in historical[espn_id]:
                if canonical(player['team']) == team_code and player.get('player'):
                    espn_by_name[normalize(player['player'])].append(str(player['player_id']))
            for name in nba_by_name.keys() & espn_by_name.keys():
                if len(nba_by_name[name]) == len(espn_by_name[name]) == 1:
                    pair = espn_by_name[name][0], nba_by_name[name][0]
                    evidence[pair].append({'espn_game_id': espn_id, 'nba_game_id': nba_id,
                                           'team': team_code, 'normalized_name': name})
    espn_links, nba_links = defaultdict(set), defaultdict(set)
    for espn, nba in evidence:
        espn_links[espn].add(nba)
        nba_links[nba].add(espn)
    links = {espn: {'nba_player_id': nba, 'observations': evidence[espn, nba]}
             for espn, nba in sorted(evidence)
             if len(espn_links[espn]) == len(nba_links[nba]) == 1}

    fixtures = []
    for fixture in snapshot['predictions']:
        if utc(emitted) >= utc(fixture['tipoff_utc']):
            continue
        gid = str(fixture['game_id'])
        teams = availability['games'].get(gid, {}).get('teams', {})
        for team, row in sorted(teams.items()):
            observed = row.get('observed_at_utc')
            if not observed or not utc(observed) <= utc(emitted):
                continue
            players = row['players']
            mapped = {p['player_id']: links[p['player_id']]['nba_player_id']
                      for p in players if p['player_id'] in links}
            fixtures.append({'game_id': gid, 'team': team, 'player_ids': mapped,
                             'unresolved_espn_ids': sorted(p['player_id'] for p in players
                                                           if p['player_id'] not in mapped)})
    report = {'baseline_snapshot_sha256': snapshot['content_sha256'], 'observed_at_utc': emitted,
              'team_metrics_sha256': digest(metrics), 'availability_files': manifest,
              'links': links, 'ambiguous_espn_ids': sorted(set(espn_links) - set(links)),
              'fixtures': fixtures}
    return {**report, 'content_sha256': digest(report)}
