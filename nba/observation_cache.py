"""Digest-verified, create-only per-game postgame observations."""
import hashlib
import json
from pathlib import Path


def location(root, game):
    gid=str(game['game_id'])
    if not gid.isdigit():
        raise ValueError('Unsafe game ID in observation cache')
    return Path(root)/(gid+'.json')


def read(root, game):
    path=location(root,game)
    if not path.exists():return None
    record=json.loads(path.read_text())
    body={k:v for k,v in record.items() if k!='sha256'}
    if record['fixture']!=game or hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()!=record.get('sha256'):
        raise ValueError('Observation cache integrity/fixture mismatch')
    return record['data']


def save(root, game, data):
    path=location(root,game)
    path.parent.mkdir(parents=True,exist_ok=True)
    record={'schema_version':1,'fixture':game,'data':data}
    record['sha256']=hashlib.sha256(json.dumps(record,sort_keys=True,allow_nan=False).encode()).hexdigest()
    with path.open('x') as target:json.dump(record,target,indent=2,allow_nan=False)
