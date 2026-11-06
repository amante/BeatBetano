"""Create-only NBA source capture: sports facts, identities and score-path audit.

Historical targets never become pregame injuries. No raw bookmaker/news payloads
are retained. Unlisted roster members stay unknown, even with an official PDF.
"""
import argparse
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from current_feed import parse_current
from espn_games import BASE
from espn_current_roster_feed import collect as rosters
from lineup_live_collector import collect as lineups
from official_injury_pdf import report_datetime
from official_injury_table import extract as injury_rows
from player_status_intake import normalize
from player_game_history import parse_boxscore, SUMMARY
from possession_intelligence import extract as team_boxscore
from reproducible_slate import digest
from prospective import utc
from team_identity import canonical


def now():
    return datetime.now(timezone.utc).isoformat()


def save_new(root, name, value):
    path = Path(root)/name
    path.parent.mkdir(parents=True,exist_ok=True)
    raw = json.dumps(value,indent=2,allow_nan=False).encode()
    with path.open('xb') as f:
        f.write(raw)
    return hashlib.sha256(raw).hexdigest()


def pdf_table_pages(raw):
    """Reconstruct visual rows from PDF coordinates, including inverted CTMs.

    The NBA PDF can have negative font size / inverted coordinates; pypdf's
    layout extractor then reverses rows. This keeps the original parser and
    normalizes only the extraction geometry.
    """
    from pypdf import PdfReader
    result = []
    for page in PdfReader(io.BytesIO(raw)).pages:
        lines = {}
        def visit(text, cm, tm, font, size):
            if not text.strip():
                return
            x = tm[4]*cm[0]+tm[5]*cm[2]+cm[4]
            y = tm[4]*cm[1]+tm[5]*cm[3]+cm[5]
            lines.setdefault(round(y,1),[]).append((x,text.strip()))
        page.extract_text(visitor_text=visit)
        result.append('\n'.join(' '.join(t for x,t in sorted(values))
                                for y,values in sorted(lines.items(),reverse=True)))
    return result


def sports_summary(payload):
    """Whitelist event/team/player statistics and action facts; discard markets."""
    header = payload['header']
    competitions = []
    for comp in header['competitions']:
        competitors = []
        for c in comp['competitors']:
            competitors.append({k:c[k] for k in ('homeAway','score') if k in c})
            competitors[-1]['team'] = {k:c['team'][k] for k in ('id','abbreviation','displayName') if k in c['team']}
        competitions.append({k:comp[k] for k in ('id','date','status') if k in comp})
        competitions[-1]['competitors'] = competitors
    box = payload['boxscore']
    teams = [{k:g[k] for k in ('team','statistics') if k in g} for g in box['teams']]
    players = []
    for group in box['players']:
        blocks = []
        for b in group.get('statistics',[]):
            block = {k:b[k] for k in ('labels','names','keys','descriptions') if k in b}
            block['athletes'] = []
            for p in b.get('athletes',[]):
                row = {k:p[k] for k in ('stats','starter','didNotPlay','reason') if k in p}
                row['athlete'] = {k:p['athlete'][k] for k in ('id','displayName','position') if k in p['athlete']}
                block['athletes'].append(row)
            blocks.append(block)
        players.append({'team':{k:group['team'][k] for k in ('id','abbreviation','displayName') if k in group['team']},
                        'statistics':blocks})
    plays = []
    allowed = ('id','sequenceNumber','type','text','homeScore','awayScore','period','clock',
               'scoringPlay','scoreValue','team','participants','wallclock','shootingPlay','pointsAttempted')
    for event in payload.get('plays',[]):
        plays.append({k:event[k] for k in allowed if k in event})
    return {'header':{'competitions':competitions},'boxscore':{'teams':teams,'players':players},'plays':plays}


def score_path(payload, game):
    """Certify observed scoring transitions, not normalized possession endings."""
    plays = payload.get('plays',[])
    if not plays:
        raise ValueError('Missing full play-by-play')
    h = a = mh = ma = 0
    seen = set()
    periods = set()
    previous_time = (-1,0)
    for p in plays:
        pid = str(p['id'])
        clock = p['clock']['displayValue']
        match = re.fullmatch(r'(\d+):(\d{2}(?:\.\d+)?)',clock)
        if match and float(match[2]) < 60:
            seconds = int(match[1])*60+float(match[2])
        elif re.fullmatch(r'\d{1,2}(?:\.\d+)?',clock) and float(clock) < 60:
            seconds = float(clock)
        else:
            raise ValueError('Unrecognized game clock')
        period = p['period']['number']
        if type(period) is not int or period < 1 or seconds > (720 if period <= 4 else 300):
            raise ValueError('Invalid period clock')
        moment = (period,-seconds)
        # Provider sequence IDs can go backwards after insertion/correction.
        # Validate actual period/clock order and retain original source order.
        if pid in seen or moment < previous_time:
            raise ValueError('Duplicate or nonchronological action')
        seen.add(pid)
        previous_time = moment
        periods.add(p['period']['number'])
        nh,na = p['homeScore'],p['awayScore']
        if any(type(v) is not int for v in (nh,na)):
            raise ValueError('Noninteger score')
        delta = (nh-h,na-a)
        if min(delta) < 0 or max(delta) > 4 or (delta[0] and delta[1]):
            raise ValueError('Score correction or missing scoring actions')
        if sum(delta) != p.get('scoreValue',0) or bool(sum(delta)) != p.get('scoringPlay',False):
            raise ValueError('Scoring transition does not match action')
        h,a = nh,na
        mh,ma = max(mh,h-a),max(ma,a-h)
    end = str(plays[-1].get('type',{}).get('text','')).lower()
    text = str(plays[-1].get('text','')).lower()
    if 'end' not in end+' '+text or 'game' not in end+' '+text:
        raise ValueError('Missing end-of-game action')
    if periods != set(range(1,max(periods)+1)) or max(periods) < 4:
        raise ValueError('Incomplete period coverage')
    if plays[0]['homeScore'] or plays[0]['awayScore'] or plays[0]['period']['number'] != 1:
        raise ValueError('Truncated start of game')
    if (h,a) != (game['home_points'],game['away_points']):
        raise ValueError('Final score disagrees with scoreboard')
    return {'scoring_transitions_reconciled':True,'source_action_count':len(plays),
            'home_max_lead':mh,'away_max_lead':ma,'duration_minutes':48+5*(max(periods)-4),
            'normalized_possessions_available':False,
            'note':'Scoring-path targets only; shot/free-throw/rebound actions are not possessions.'}


def roster_name_key(value):
    """Only presentation punctuation varies; preserve all name/suffix tokens."""
    return " ".join(re.sub(r'[,.]', '', normalize(value)).split())


def resolve_official(rows, roster, fixtures, published, observed):
    output = []
    unmatched = []
    for g in fixtures:
        for team in (g['home_team'],g['away_team']):
            members = roster.get('games',{}).get(str(g['game_id']),{}).get('teams',{}).get(team,{}).get('players',[])
            lookup = {}
            for p in members:
                lookup.setdefault(roster_name_key(p['player']),[]).append(p['player_id'])
            mapped = {}
            for row in rows:
                if canonical(row['team']) != canonical(team):
                    continue
                # Reports contain multiple dates; match the fixture's local league date.
                from zoneinfo import ZoneInfo
                day = utc(g['tipoff_utc']).astimezone(ZoneInfo('America/New_York')).strftime('%m/%d/%Y')
                if row.get('game_date') != day:
                    continue
                if not utc(published) <= utc(observed) < utc(g['tipoff_utc']):
                    continue
                ids = lookup.get(roster_name_key(row['player']),[])
                if len(ids) != 1:
                    unmatched.append({'game_id':g['game_id'],'team':team,'player':row['player'],'reason':'not_unique_exact_normalized_roster_match'})
                    continue
                pid = ids[0]
                if pid in mapped and mapped[pid]['official_status'] != row['status']:
                    raise ValueError('Conflicting official statuses')
                mapped[pid] = {'player_id':pid,'player':row['player'],'official_status':row['status'],
                               'published_at_utc':published,'observed_at_utc':observed,
                               'page':row['page'],'line':row['line'],'identity_match':'unique_team_and_punctuation_normalized_name'}
            output.append({'game_id':str(g['game_id']),'team':team,'roster_members':len(members),
                           'official_claims':list(mapped.values()),
                           'unlisted_player_ids':[p['player_id'] for p in members if p['player_id'] not in mapped],
                           'unlisted_status':'unknown','complete_active_roster_verified':False})
    return {'teams':output,'unmatched_claims':unmatched,'unlisted_means_healthy':False}


def capture(day, historical, output, official_url, workers=4):
    if not 1 <= workers <= 4:
        raise ValueError('Use one to four source requests in parallel')
    root = Path(output)
    root.mkdir(parents=True,exist_ok=False)
    errors = []
    response = requests.get(BASE,params={'dates':day.replace('-',''),'limit':500,'seasontype':2},timeout=25)
    response.raise_for_status()
    scoreboard_at = now()
    current = parse_current(response.json(),scoreboard_at)
    save_new(root,'schedule.json',current)
    cohort = {'created_at_utc':now(),'predictions':current['future_fixtures']}
    cohort['content_sha256'] = digest(cohort)
    save_new(root,'fixture_cohort.json',cohort)
    roster = rosters(cohort)
    roster_at = now()
    for g in roster.get('games',{}).values():
        for t in g.get('teams',{}).values():
            if t.get('observed_at_utc'):
                t['observed_at_utc'] = roster_at
    save_new(root,'rosters.json',roster)
    selected,candidates = lineups(cohort)
    # Restamp at response completion, never before the actual source request.
    lineup_at = now()
    for g in selected['games'].values():
        for t in g['teams'].values():
            if t.get('observed_at_utc'):
                t['observed_at_utc'] = lineup_at
    for c in candidates['candidates']:
        c['observed_at_utc'] = lineup_at
    save_new(root,'lineups.json',selected)
    save_new(root,'lineup_candidates.json',candidates)
    try:
        host = urlparse(official_url).hostname
        published = report_datetime(official_url)
        if host != 'ak-static.cms.nba.com' or not published or published > utc(now()):
            raise ValueError('Require an already published NBA official PDF URL')
        r = requests.get(official_url,timeout=30)
        r.raise_for_status()
        if not r.content.startswith(b'%PDF-'):
            raise ValueError('Expected actual PDF bytes')
        pages = pdf_table_pages(r.content)
        observed = now()
        with (root/'official_injury.pdf').open('xb') as f:
            f.write(r.content)
        rows = injury_rows(pages, continuous_table=True)
        official = {'report_url':official_url,'published_at_utc':published.isoformat(),
                    'observed_at_utc':observed,'pdf_sha256':hashlib.sha256(r.content).hexdigest(),
                    'raw_page_text':pages,'rows':rows,'pages':len(pages)}
        save_new(root,'official_injury.json',official)
        resolved = resolve_official(rows,roster,cohort['predictions'],published.isoformat(),observed)
        save_new(root,'official_status_resolution.json',resolved)
    except (requests.RequestException,ValueError,ImportError) as exc:
        official = {}
        resolved = {'teams':[],'unmatched_claims':[]}
        errors.append({'scope':'official_injury','type':type(exc).__name__,'detail':str(exc)[:500]})
    # History is a list of prior fixtures, never an availability ledger.
    season_end = int(day[:4])+int(int(day[5:7]) >= 10)
    fixtures = {str(g['game_id']):g for g in historical if int(g['season']) == season_end}
    # Include the latest completed league day, independently fetched now.
    from datetime import date,timedelta
    prior_day = (date.fromisoformat(day)-timedelta(days=1)).strftime('%Y%m%d')
    r = requests.get(BASE,params={'dates':prior_day,'limit':500,'seasontype':2},timeout=25)
    r.raise_for_status()
    prior = parse_current(r.json(),now())
    save_new(root,'previous_day_schedule.json',prior)
    for g in prior['completed_games']+current['completed_games']:
        fixtures[str(g['game_id'])] = g
    cutoff = utc(now())
    games = sorted([g for g in fixtures.values() if utc(g['tipoff_utc']) < cutoff and g['home_points'] is not None],
                   key=lambda g:(utc(g['tipoff_utc']),str(g['game_id'])))
    def one(g):
        gid = str(g['game_id'])
        try:
            r = requests.get(SUMMARY,params={'event':gid},timeout=25)
            r.raise_for_status()
            sports = sports_summary(r.json())
            observed = now()
            players = parse_boxscore(sports,g,observed)
            stats = team_boxscore(sports,g)
            comp = sports['header']['competitions'][0]
            scores = {c['team']['abbreviation']:int(c['score']) for c in comp['competitors']}
            if scores != {g['home_team']:g['home_points'],g['away_team']:g['away_points']}:
                raise ValueError('Summary/scoreboard final-score disagreement')
            raw_hash = save_new(root,'sports_summaries/'+gid+'.json',sports)
            path = None
            gap = None
            try:
                path = score_path(sports,g)
            except (KeyError,TypeError,ValueError) as exc:
                gap = str(exc)
            return {'game':g,'source_url':SUMMARY+'?event='+gid,'observed_at_utc':observed,
                    'sports_payload_sha256':raw_hash,'team_statistics':stats,'players':players,
                    'score_path':path,'score_path_gap':gap}
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            return {'game_id':gid,'error_type':type(exc).__name__,'detail':str(exc)[:500]}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        collected = list(pool.map(one,games))
    good = [r for r in collected if 'game' in r]
    errors += [r for r in collected if 'game' not in r]
    save_new(root,'historical_boxscores.json',{'games':good,'source':SUMMARY})
    summary = {'captured_at_utc':now(),'target_date':day,'future_games':len(cohort['predictions']),
               'current_roster_players':sum(len(t.get('players',[])) for g in roster.get('games',{}).values() for t in g.get('teams',{}).values()),
               'official_document_retrieved':bool(official),'official_parsed_rows':len(official.get('rows',[])),
               'official_claims_matched':sum(len(t['official_claims']) for t in resolved['teams']),
               'official_claims_unmatched':len(resolved['unmatched_claims']),
               'lineup_teams_observed':sum(bool(t.get('starters')) for g in selected['games'].values() for t in g['teams'].values()),
               'lineup_teams_confirmed':sum(t.get('lineup_status') == 'confirmed' for g in selected['games'].values() for t in g['teams'].values()),
               'historical_games_requested':len(games),'historical_games_collected':len(good),
               'historical_player_rows':sum(len(g['players']) for g in good),
               'reconciled_score_paths':sum(g['score_path'] is not None for g in good),
               'score_path_gaps':[{'game_id':g['game']['game_id'],'reason':g['score_path_gap']} for g in good if g['score_path_gap']],
               'errors':errors,'roster_source_errors':roster.get('errors',[]),'lineup_source_errors':selected.get('fetch_errors',[]),
               'recommendation':'PASS','production_approved':False,
               'remaining':['Confirmed starting fives and complete active status for both teams',
                            'Normalized possession endings (raw plays are archived)',
                            'Opponent-adjusted player effects, replacement roles and independent validation'],
               'no_odds_input':True,'historical_observations_are_not_pregame_injuries':True}
    save_new(root,'summary.json',summary)
    manifest = {'created_at_utc':now(),'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.rglob('*')) if p.is_file()}}
    save_new(root,'manifest.json',manifest)
    return summary


def replay_capture(source, output):
    """Re-derive facts from immutable captured source bytes, without network."""
    source,root = Path(source),Path(output)
    manifest = json.loads((source/'manifest.json').read_text())
    for name,sha in manifest['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or hashlib.sha256((source/relative).read_bytes()).hexdigest() != sha:
            raise ValueError('Source manifest mismatch')
    root.mkdir(parents=True,exist_ok=False)
    load = lambda name:json.loads((source/name).read_text())
    cohort,roster = load('fixture_cohort.json'),load('rosters.json')
    raw = (source/'official_injury.pdf').read_bytes()
    original = load('official_injury.json')
    if hashlib.sha256(raw).hexdigest() != original['pdf_sha256']:
        raise ValueError('Official PDF digest mismatch')
    pages = pdf_table_pages(raw)
    rows = injury_rows(pages, continuous_table=True)
    save_new(root,'official_injury_reparsed.json',{**original,'raw_page_text':pages,'rows':rows,
             'extraction_method':'pypdf_visual_coordinate_rows_v1','reprocessed_at_utc':now()})
    statuses = resolve_official(rows,roster,cohort['predictions'],original['published_at_utc'],original['observed_at_utc'])
    save_new(root,'official_status_resolution.json',statuses)
    history = load('historical_boxscores.json')['games']
    paths = []
    gaps = []
    by_player = {}
    for row in history:
        g = row['game']
        payload = load('sports_summaries/'+str(g['game_id'])+'.json')
        try:
            paths.append({'game':g,'observed_at_utc':row['observed_at_utc'],
                          'sports_payload_sha256':row['sports_payload_sha256'],**score_path(payload,g)})
        except (KeyError,TypeError,ValueError) as exc:
            gaps.append({'game_id':g['game_id'],'reason':str(exc)})
        for p in row['players']:
            if not p['did_not_play'] and p['minutes_played'] is not None:
                by_player.setdefault((canonical(p['team']),p['player_id']),[]).append({
                    'game_id':str(g['game_id']),'tipoff_utc':g['tipoff_utc'],
                    'minutes':p['minutes_played'],'observed_at_utc':row['observed_at_utc']})
    save_new(root,'score_paths.json',{'games':paths,'gaps':gaps,
             'available_at_utc':now(),'pregame_availability_known':False})
    coverage = []
    for g in cohort['predictions']:
        for t in (g['home_team'],g['away_team']):
            players = roster.get('games',{}).get(str(g['game_id']),{}).get('teams',{}).get(t,{}).get('players',[])
            claims = next((r for r in statuses['teams'] if r['game_id'] == str(g['game_id']) and r['team'] == t),{})
            mapped = {p['player_id']:p for p in claims.get('official_claims',[])}
            rows_out = []
            for p in players:
                prior = sorted([r for r in by_player.get((canonical(t),p['player_id']),[])
                                if utc(r['tipoff_utc']) < utc(cohort['created_at_utc'])
                                and utc(r['observed_at_utc']) < utc(g['tipoff_utc'])],key=lambda r:utc(r['tipoff_utc']))
                last = prior[-5:]
                claim = mapped.get(p['player_id'])
                rows_out.append({**p,'official_status':claim['official_status'] if claim else 'unknown',
                                 'prior_appearances':len(prior),
                                 'last_five_observed_mean_minutes':sum(x['minutes'] for x in last)/len(last) if len(last)>=3 else None,
                                 'prior_game_ids':[x['game_id'] for x in last],
                                 'projected_minutes':None,'adjusted_on_off':None,'replacement_quality':None})
            coverage.append({'game_id':str(g['game_id']),'team':t,'players':rows_out,
                             'recommendation':'PASS','full_active_roster_verified':False})
    save_new(root,'player_feature_coverage.json',{'teams':coverage,'created_at_utc':now(),
             'historical_minutes_are_not_projected_minutes':True})
    result = {'created_at_utc':now(),'source_capture':source.name,
              'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
              'official_parsed_rows':len(rows),'official_claims_matched':sum(len(t['official_claims']) for t in statuses['teams']),
              'official_claims_unmatched':len(statuses['unmatched_claims']),
              'reconciled_score_paths':len(paths),'score_path_gaps':gaps,
              'current_roster_members':sum(len(t['players']) for t in coverage),
              'players_with_minute_history':sum(p['last_five_observed_mean_minutes'] is not None for t in coverage for p in t['players']),
              'recommendation':'PASS','normalized_possessions_available':False,
              'independent_player_impact_validation_available':False}
    save_new(root,'summary.json',result)
    save_new(root,'manifest.json',{'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}})
    return result


def main():
    p = argparse.ArgumentParser()
    for key in ('date','history','official-report-url','replay-capture'):
        p.add_argument('--'+key)
    p.add_argument('--output',required=True)
    p.add_argument('--workers',type=int,default=4)
    a = p.parse_args()
    if a.replay_capture:
        result = replay_capture(a.replay_capture,a.output)
    else:
        if not all((a.date,a.history,a.official_report_url)):
            p.error('Require --date, --history and --official-report-url for live capture')
        result = capture(a.date,json.loads(Path(a.history).read_text()),a.output,a.official_report_url,a.workers)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
