"""Public display context and frozen player identity observations; no fitted model effects."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from nhl.nhlcom_projected_lineup_capture import Text, URL


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'PULSO-match-context/1.0'}), timeout=20) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000: raise ValueError('Oversized source')
    return raw


def label(value):
    return value.get('default', '') if isinstance(value, dict) else value if isinstance(value, str) else ''


def article_matches_fixture(published, start, max_age_hours=24):
    """Accept the current editorial slate by time, including Chile midnight rollovers."""
    age = start - published
    return timedelta(0) <= age <= timedelta(hours=max_age_hours)


def editorial(raw, now):
    html = raw.decode('utf-8')
    dates = []
    for script in re.findall(r'<script[^>]*type="application/ld[^>]*>(.*?)</script>', html, re.S):
        try: obj = json.loads(unescape(script))
        except ValueError: continue
        if isinstance(obj, dict) and obj.get('@type') == 'NewsArticle':
            dates.append(datetime.fromisoformat(obj['dateModified'].replace('Z', '+00:00')))
    if len(dates) != 1 or dates[0] > now: raise ValueError('Unverified article timestamp')
    parser = Text(); parser.feed(html)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in ''.join(parser.parts).splitlines()]
    blocks, block = {}, None
    for line in lines:
        heading = re.fullmatch(r'(.+?) projected lineup', line, re.I)
        if heading:
            name = heading[1].casefold()
            if name in blocks: raise ValueError('Ambiguous editorial heading')
            block = dict(forwards=[], defense=[], goalies=[], injuries=None, scratches=None)
            blocks[name] = block
            continue
        if block is None or not line: continue
        if line == 'Status report': block = None; continue
        if line.startswith(('Scratched:', 'Injured:')):
            key = 'scratches' if line.startswith('Scratched:') else 'injuries'
            value = line.split(':', 1)[1].strip()
            block[key] = [] if value.casefold() == 'none' else [s.strip() for s in value.split(',') if s.strip()]
            continue
        if block['scratches'] is not None or block['injuries'] is not None: continue
        line = re.sub(r'\s+-\s+-\s+', ' -- ', line)
        names = re.split(r'\s+(?:--|–|—|-)\s+', line)
        if len(names) == 3 and len(block['forwards']) < 4: block['forwards'].append(names)
        elif len(names) == 2 and len(block['defense']) < 3: block['defense'].append(names)
        elif len(names) == 1 and len(block['forwards']) == 4 and len(block['defense']) == 3 and len(block['goalies']) < 2:
            if re.fullmatch(r"[\w .’'\-]+", line): block['goalies'].append(line)
    return dates[0], blocks


def build(schedule, raw_article, get=fetch, now=None):
    live_capture = now is None
    now = now or datetime.now(timezone.utc)
    errors, blocks, published = [], {}, None
    try: published, blocks = editorial(raw_article, now)
    except (ValueError, KeyError, UnicodeError): errors.append('Lineups unavailable or unverified article date')
    def game_context(g):
        row = dict(game_id=g['id'], home=g['home'], away=g['away'], start_utc=g['start_utc'], venue=g.get('venue'), city=None, teams={}, referees=[], linesmen=[], sources=[], errors=[])
        start = datetime.fromisoformat(g['start_utc'].replace('Z', '+00:00'))
        # Current observations cannot supply a historical pregame context.
        if start <= now:
            row['errors'].append('Pregame context not captured before start'); return row
        for endpoint in ('landing', 'right-rail'):
            url = 'https://api-web.nhle.com/v1/gamecenter/' + g['id'] + '/' + endpoint
            try:
                raw = get(url); obj = json.loads(raw)
                if endpoint == 'landing':
                    if str(obj['id']) != g['id'] or obj['homeTeam']['abbrev'] != g['home'] or obj['awayTeam']['abbrev'] != g['away'] or obj['startTimeUTC'] != g['start_utc']: raise ValueError('Fixture mismatch')
                    row['venue'], row['city'] = label(obj.get('venue')), label(obj.get('venueLocation'))
                else:
                    # Endpoint is game-ID scoped; retain role labels and never infer missing names.
                    info = obj.get('gameInfo', {})
                    for key in ('referees', 'linesmen'):
                        row[key] = [label(p.get('name')) for p in info.get(key, []) if isinstance(p, dict) and label(p.get('name'))]
                row['sources'].append(dict(url=url, sha256=hashlib.sha256(raw).hexdigest()))
            except Exception:
                row['errors'].append(endpoint + ' unavailable or invalid')
        # Exact source common-name match, both fixture teams, and Chile game-date gate.
        day = start.astimezone(ZoneInfo('America/Santiago')).date()
        names = {code: g.get(side + '_name', '').casefold() for side, code in [('home', g['home']), ('away', g['away'])]}
        eligible = published and article_matches_fixture(published, start) and all(n and n in blocks for n in names.values())
        if eligible:
            for code, name in names.items():
                b = blocks[name]
                if len(b['forwards']) != 4 or len(b['defense']) != 3: continue
                row['teams'][code] = dict(**b, status='projected', starting_goalie=None, starting_goalie_status='unconfirmed')
            row['sources'].append(dict(url=URL, sha256=hashlib.sha256(raw_article).hexdigest(), published_at=published.isoformat()))
        return row
    with ThreadPoolExecutor(max_workers=4) as pool: games = list(pool.map(game_context, schedule['games']))
    return dict(kind='nhl_match_context_v1', as_of_utc=(datetime.now(timezone.utc) if live_capture else now).isoformat(), model_features_used=False, games=games, errors=errors)



def player_evidence(report, rosters, crosswalk, goalie_history, raw_article, as_of):
    """Resolve projected deployment to IDs; missing data stays null, never neutral."""
    from nhl.pulso_pregame_v7 import parse_utc
    from nhl.nhlcom_lineup_identity import normalized
    from nhl.pulso_goalie_multisource_257 import TEAM_NAMES
    issued = parse_utc(as_of)
    if report.get('data_kind') != 'source_readiness_only' or parse_utc(report['generated_at_utc']) > issued:
        raise ValueError('Invalid source report or future capture')
    if parse_utc(crosswalk['retrieved_at']) > issued: raise ValueError('Future goalie crosswalk')
    roster_by_team = {}
    for row in rosters:
        if row['team'] in roster_by_team: raise ValueError('Duplicate roster')
        if parse_utc(row['as_of']) > issued: raise ValueError('Future roster')
        if not row.get('source_url', '').startswith('https://api-web.nhle.com/v1/roster/') or not re.fullmatch(r'[a-f0-9]{64}', row.get('source_sha256', '')):
            raise ValueError('Missing official roster provenance')
        roster_by_team[row['team']] = row
    try: published, blocks = editorial(raw_article, issued)
    except (ValueError, KeyError, UnicodeError): published, blocks = None, {}
    # Source reports use common-name headings; only unique suffix matches of the
    # explicit NHL team registry are admitted (no fuzzy player/team guessing).
    def team_block(team):
        matches = [b for name, b in blocks.items() if normalized(TEAM_NAMES[team]).endswith(' '+normalized(name))]
        return matches[0] if len(matches) == 1 else None
    history_games = {str(g['game_id']): g for g in goalie_history.get('games', [])}
    if len(history_games) != len(goalie_history.get('games', [])): raise ValueError('Duplicate goalie history fixture')
    output, skipped, seen = [], [], set()
    for fixture in report['games']:
        gid = str(fixture['game_id'])
        if gid in seen: raise ValueError('Duplicate fixture')
        seen.add(gid)
        start = parse_utc(fixture['start_utc'])
        if issued >= start:
            skipped.append(gid); continue
        codes = (fixture['home'], fixture['away'])
        day = start.astimezone(ZoneInfo('America/Santiago')).date()
        mapped = published and article_matches_fixture(published, start) and all(team_block(t) for t in codes)
        sides = {}
        for team in codes:
            roster = roster_by_team.get(team)
            players = roster.get('players', []) if roster else []
            identities = {}
            for p in players:
                identities.setdefault(normalized(p['full_name']), []).append(p)
            def resolve_name(name, role=None):
                name_only = re.sub(r'\s*\([^)]*\)', '', name).strip()
                requested = normalized(name_only)
                eligible = [p for p in players if role is None or p['position_group'] == role]
                exact = [p for p in identities.get(requested, []) if p in eligible]
                match, method = (exact[0], 'exact') if len(exact) == 1 else (None, None)
                if not exact and not match:
                    parts = requested.split()
                    aliases = {'mikey': {'michael'}, 'philip': {'filip'}, 'filip': {'philip'}}
                    nick = []
                    if len(parts) >= 2:
                        for p in eligible:
                            candidate = normalized(p['full_name']).split()
                            if len(candidate) == len(parts) and candidate[-1] == parts[-1] and candidate[0] in aliases.get(parts[0], set()) and candidate[1:-1] == parts[1:-1]:
                                nick.append(p)
                    if len(nick) == 1:
                        match, method = nick[0], 'recognized_first_name_variant'
                def one_edit(a, b):
                    if abs(len(a) - len(b)) > 1: return False
                    i = j = edits = 0
                    while i < len(a) and j < len(b):
                        if a[i] == b[j]: i += 1; j += 1; continue
                        edits += 1
                        if edits > 1: return False
                        if len(a) == len(b): i += 1; j += 1
                        elif len(a) > len(b): i += 1
                        else: j += 1
                    edits += (len(a) - i) + (len(b) - j)
                    return edits <= 1
                if not match and not exact and role is not None:
                    near = [p for p in eligible if one_edit(requested, normalized(p['full_name']))]
                    if len(near) == 1:
                        match, method = near[0], 'unique_single_character_correction'
                return dict(name=name, player_id=match['player_id'] if match else None,
                    identity_resolved=match is not None, identity_match_method=method)
            block = team_block(team) if mapped else None
            groups = {}
            for field, role in [('forwards', 'forward'), ('defense', 'defense'), ('goalies', 'goalie')]:
                raw = block.get(field) if block else None
                if field == 'goalies': groups[field] = [resolve_name(n, role) for n in raw] if raw is not None else None
                else: groups[field] = [[resolve_name(n, role) for n in line] for line in raw] if raw is not None else None
            for field in ('injuries', 'scratches'):
                raw = block.get(field) if block else None
                groups[field] = [resolve_name(n) for n in raw] if raw is not None else None
            skaters = [p for key in ('forwards','defense') for line in groups[key] or [] for p in line]
            ids = [p['player_id'] for p in skaters if p['identity_resolved']]
            duplicates = len(ids) != len(set(ids))
            complete = bool(block and len(groups['forwards'])==4 and len(groups['defense'])==3 and len(skaters)==18 and len(ids)==18 and not duplicates)
            absent_ids = {p['player_id'] for field in ('injuries','scratches') for p in groups[field] or [] if p['identity_resolved']}
            conflict = bool(set(ids) & absent_ids)
            complete = complete and not conflict
            unresolved_skaters = [p['name'] for p in skaters if not p['identity_resolved']]
            line_shape_complete = bool(block and len(groups['forwards']) == 4 and len(groups['defense']) == 3 and len(skaters) == 18)
            if not block: lineup_capture_status = 'source_unavailable'
            elif not line_shape_complete: lineup_capture_status = 'projected_lines_incomplete'
            elif complete: lineup_capture_status = 'projected_identity_complete'
            else: lineup_capture_status = 'projected_identity_partial'
            candidates = [g for g in crosswalk.get('observations', []) if str(g.get('nhl_game_id'))==gid and g.get('team')==team and g.get('usable_pregame_identity') is True and not g.get('validation_errors') and g.get('matchup_verified') is True]
            usable = []
            for g in candidates:
                if g.get('event_start') is None or parse_utc(g['event_start']) != start: continue
                captured = parse_utc(g.get('source_captured_at'))
                if captured > issued or captured >= start: continue
                if roster and captured < parse_utc(roster['as_of']): continue
                found = [p for p in players if p['player_id']==g.get('nhl_player_id') and p['position_group']=='goalie']
                if len(found)==1: usable.append(g)
            goalie = usable[0] if len(usable)==1 else None
            history = history_games.get(gid, {})
            if history and (history.get('home'), history.get('away')) != codes: raise ValueError('Goalie history fixture mismatch')
            h = history.get('teams', {}).get(team, {})
            statistics = None
            if goalie and h.get('nhl_player_id')==goalie['nhl_player_id'] and h.get('status')=='observed':
                source, m = h.get('source', {}), h.get('metrics', {})
                retrieved = parse_utc(source.get('retrieved_at'))
                if retrieved <= issued and retrieved < start and m.get('cutoff_exclusive', '') == parse_utc(report['generated_at_utc']).date().isoformat():
                    # The existing #251 collector validates the official log and
                    # excludes same-day results; retain both rates and sample sizes.
                    expected_url = 'https://api-web.nhle.com/v1/player/'+str(goalie['nhl_player_id'])+'/game-log/'
                    def valid_metric(v):
                        import math
                        return (all(type(v.get(k)) is int for k in ('games','shots_against','saves')) and v['games']>0 and v['shots_against']>0 and 0<=v['saves']<=v['shots_against'] and type(v.get('save_pct')) in (int,float) and math.isfinite(v['save_pct']) and abs(v['save_pct']-v['saves']/v['shots_against'])<0.00001)
                    if not source.get('url','').startswith(expected_url) or not re.fullmatch(r'[a-f0-9]{64}',source.get('sha256','')) or not all(valid_metric(m.get(key,{})) for key in ('season_to_date','last_5_games')):
                        raise ValueError('Malformed prior goalie statistics')
                    statistics = dict(season_to_date=m['season_to_date'], last_5_games=m['last_5_games'], source=source, cutoff_exclusive=m['cutoff_exclusive'])
            blockers = []
            if not complete: blockers.append('projected_lines_incomplete_or_unresolved')
            if groups['injuries'] is None or any(not p['identity_resolved'] for p in groups['injuries']): blockers.append('injuries_missing_or_unresolved')
            if not goalie: blockers.append('no_unique_fixture_goalie_identity')
            if statistics is None: blockers.append('goalie_prior_statistics_missing')
            blockers += ['projected_not_confirmed_availability', 'incremental_effect_not_fitted_or_validated']
            sides[team] = dict(projected=groups, projected_skaters_identity_complete=complete,
                lineup_capture_status=lineup_capture_status,
                projected_skaters_identity_coverage=dict(captured=len(skaters), resolved=len(ids), unresolved_names=unresolved_skaters),
                duplicate_player_ids=duplicates, availability_conflict=conflict,
                roster_source={k:roster[k] for k in ('source_url','source_sha256','as_of')} if roster else None,
                goalie_player_id=goalie['nhl_player_id'] if goalie else None,
                goalie_provider_status=goalie.get('goalie_status') if goalie else None,
                goalie_source=goalie.get('source_url') if goalie else None, goalie_source_captured_at=goalie.get('source_captured_at') if goalie else None,
                independent_starter_confirmation=False, goalie_prior_statistics=statistics,
                blockers=blockers, model_eligible=False)
        output.append(dict(game_id=gid, home=codes[0], away=codes[1], start_utc=fixture['start_utc'], feature_as_of_utc=as_of,
            editorial_source=dict(url=URL, published_at=published.isoformat(), sha256=hashlib.sha256(raw_article).hexdigest()) if mapped else None,
            teams=sides, applied_probability_delta=None, training_ready=False))
    return dict(kind='nhl_pregame_player_evidence_v1', as_of_utc=as_of, games=output, skipped_started_games=skipped,
        probabilities_modified=False, automatic_promotion=False,
        status='prospective_observations_not_fitted',
        note='Projected lines and provider goalie assertions are not independently confirmed availability. Never impute missing ratings or train on the display snapshot.')


def freeze_player_evidence(directory, run_id, destination):
    """Keep original source files and resolved IDs together, append-only per run."""
    import gzip
    if not str(run_id).isdigit(): raise ValueError('Numeric run ID required')
    root = Path(directory)
    names = ['report.json','official_roster_candidates.json','goalie_identity_crosswalk.json','goalie_history_251.json','editorial_lineup_raw.html','goalie_observations.json','espn_raw.json']
    blobs = {name: (root/name).read_bytes() for name in names}
    read = lambda name: json.loads(blobs[name])
    at = datetime.now(timezone.utc).isoformat()
    result = player_evidence(read('report.json'), read('official_roster_candidates.json')['rosters'], read('goalie_identity_crosswalk.json'), read('goalie_history_251.json'), blobs['editorial_lineup_raw.html'], at)
    result['run_id'] = str(run_id)
    result['source_files_sha256'] = {name:hashlib.sha256(raw).hexdigest() for name,raw in blobs.items()}
    result['content_sha256'] = hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    output = Path(destination); output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents accidental replacement of an existing run.
    if output.exists() or output.with_suffix('.sources.json.gz').exists(): raise FileExistsError('Run evidence already exists')
    with output.open('x') as handle: json.dump(result,handle,ensure_ascii=False,indent=2)
    bundle = output.with_suffix('.sources.json.gz')
    with bundle.open('xb') as handle:
        handle.write(gzip.compress(json.dumps({name:raw.decode('utf-8') for name,raw in blobs.items()},ensure_ascii=False).encode(),mtime=0))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schedule', default='frontend/data/nhl-schedule.json')
    parser.add_argument('--output', default='frontend/data/nhl-match-context.json')
    parser.add_argument('--pregame-evidence-dir')
    parser.add_argument('--run-id')
    args = parser.parse_args()
    if args.pregame_evidence_dir:
        result = freeze_player_evidence(args.pregame_evidence_dir, args.run_id, args.output)
        print(json.dumps(dict(games=len(result['games']), status=result['status'])))
        raise SystemExit(0)
    try: article = fetch(URL)
    except Exception: article = b''
    result = build(json.loads(Path(args.schedule).read_text()), article)
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(games=len(result['games']), teams_with_projected_lines=sum(len(g['teams']) for g in result['games']))))
