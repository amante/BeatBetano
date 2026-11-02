"""Public display context; never a numerical feature or pregame confirmation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
        names = re.split(r'\s+(?:--|–|—)\s+', line)
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
        eligible = published and published.astimezone(ZoneInfo('America/Santiago')).date() == day and all(n and n in blocks for n in names.values())
        if eligible:
            for code, name in names.items():
                b = blocks[name]
                if len(b['forwards']) != 4 or len(b['defense']) != 3: continue
                row['teams'][code] = dict(**b, status='projected', starting_goalie=None, starting_goalie_status='unconfirmed')
            row['sources'].append(dict(url=URL, sha256=hashlib.sha256(raw_article).hexdigest(), published_at=published.isoformat()))
        return row
    with ThreadPoolExecutor(max_workers=4) as pool: games = list(pool.map(game_context, schedule['games']))
    return dict(kind='nhl_match_context_v1', as_of_utc=(datetime.now(timezone.utc) if live_capture else now).isoformat(), model_features_used=False, games=games, errors=errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schedule', default='frontend/data/nhl-schedule.json')
    parser.add_argument('--output', default='frontend/data/nhl-match-context.json')
    args = parser.parse_args()
    try: article = fetch(URL)
    except Exception: article = b''
    result = build(json.loads(Path(args.schedule).read_text()), article)
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(games=len(result['games']), teams_with_projected_lines=sum(len(g['teams']) for g in result['games']))))
