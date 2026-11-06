"""Frozen completed seasons and create-only daily deltas; no silent full refresh."""
import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from clean_regular import clean
from espn_games import fetch_range

ARCHIVE = Path(__file__).resolve().parents[1]/'reports/nba-2026-11-04'


def frozen_history(root=ARCHIVE):
    root = Path(root)
    manifest = json.loads((root/'manifest.json').read_text())
    raw = (root/'history.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files']['history.json']:
        raise ValueError('Frozen historical archive digest mismatch')
    rows = [g for g in json.loads(raw) if int(g['season']) in (2024,2025,2026)]
    ids = [str(g['game_id']) for g in rows]
    if len(ids) != len(set(ids)) or len(rows) != 3690:
        raise ValueError('Frozen historical coverage/identity mismatch')
    rows, audit = clean(rows)
    if set(audit['seasons']) != {'2024','2025','2026'}:
        raise ValueError('Incomplete frozen seasons')
    return rows, {**audit, 'source':'repository_frozen_archive',
                  'archive_history_sha256':hashlib.sha256(raw).hexdigest(),
                  'network_requests':0}


def daily_delta(root, start, end):
    """Cache every queried scoreboard date, including empty days; retry incomplete days."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cursor, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < cursor or last >= datetime.now(timezone.utc).date():
        raise ValueError('Delta window must contain only completed prior UTC days')
    rows, requested, reused = [], [], []
    while cursor <= last:
        path = root/(cursor.isoformat()+'.json')
        if path.exists():
            record = json.loads(path.read_text())
            body = {k:v for k,v in record.items() if k != 'sha256'}
            if (record.get('schema_version') != 1 or record.get('date') != cursor.isoformat() or record.get('source') != 'espn_daily_scoreboard'
                    or hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest() != record.get('sha256')):
                raise ValueError('Daily delta integrity mismatch')
            reused.append(cursor.isoformat())
        else:
            games, count, metadata = fetch_range(cursor,cursor)
            if count >= 500:
                raise ValueError('Potential truncated daily delta')
            # A day with unfinished regular-season games must be retried, not frozen as empty.
            for event in metadata.values():
                if event.get('season',{}).get('type') == 2:
                    if len(event.get('competitions',[])) != 1 or any(c.get('status',{}).get('completed') is not True for c in event.get('competitions',[])):
                        raise ValueError('Incomplete daily scoreboard; retry later')
            record = {'schema_version':1, 'source':'espn_daily_scoreboard',
                      'date':cursor.isoformat(), 'observed_at_utc':datetime.now(timezone.utc).isoformat(),
                      'games':games, 'raw_events':count}
            record['sha256'] = hashlib.sha256(json.dumps(record,sort_keys=True,allow_nan=False).encode()).hexdigest()
            with path.open('x') as target:
                json.dump(record,target,indent=2,allow_nan=False)
            requested.append(cursor.isoformat())
        rows.extend(record['games'])
        cursor += timedelta(days=1)
    by_id = {}
    for row in rows:
        gid = str(row['game_id'])
        if gid in by_id and by_id[gid] != row:
            raise ValueError('Conflicting historical delta')
        by_id[gid] = row
    return sorted(by_id.values(),key=lambda g:(g['tipoff_utc'],str(g['game_id']))), {
        'requested_dates':requested, 'reused_dates':reused,
        'network_requests':len(requested)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    rows, audit = frozen_history()
    target = Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(rows,indent=2))
    target.with_suffix('.provenance.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps({'games':len(rows),'network_requests':0}))


if __name__ == '__main__':
    main()
