"""Strict OpenFootball full-time ingestion (never substitute half-time scores)."""
import datetime as dt
import hashlib
import json
from pathlib import Path


def normalize(payload, season):
    rows, seen = [], set()
    for match in payload['matches']:
        score = match.get('score', {})
        score = score.get('ft') if isinstance(score, dict) else score
        if score is None:
            continue
        if not isinstance(score, list) or len(score) != 2 or any(type(x) is not int or x < 0 for x in score):
            raise ValueError('Invalid full-time score')
        date = dt.date.fromisoformat(match['date']).isoformat()
        home, away = match['team1'].strip(), match['team2'].strip()
        key = season + ':' + home + ':' + away
        if not home or not away or home == away or key in seen:
            raise ValueError('Invalid or duplicate fixture')
        seen.add(key)
        rows.append(dict(id=key, season=season, date=date, home=home, away=away, hg=score[0], ag=score[1]))
    return sorted(rows, key=lambda r: (r['date'], r['id']))


def load_history(directory):
    rows, manifest = [], []
    for path in sorted(Path(directory).glob('*.json')):
        raw = path.read_bytes()
        games = normalize(json.loads(raw), path.stem)
        teams = {r[t] for r in games for t in ('home', 'away')}
        expected = {(a, b) for a in teams for b in teams if a != b}
        if len(teams) != 20 or {(r['home'], r['away']) for r in games} != expected:
            raise ValueError('Incomplete double round-robin: ' + path.stem)
        rows.extend(games)
        manifest.append(dict(season=path.stem, games=len(games), teams=len(teams), sha256=hashlib.sha256(raw).hexdigest(), source='https://github.com/openfootball/football.json/blob/master/' + path.stem + '/en.1.json'))
    return rows, manifest
