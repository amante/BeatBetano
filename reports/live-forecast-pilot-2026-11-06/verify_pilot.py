"""Read-only replay of the live pilot's archive integrity checks."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from multisport.daily_forecasts import latest
from multisport.forecast_revisions import verify_snapshot
from multisport.contract import utc


def verify(root):
    root=Path(root)
    initial=json.loads((root/'first-archive-manifest.json').read_text())['files']
    for name,sha in initial.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Unsafe archive manifest path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('Initial forecast modified: '+name)
    rows=[]
    for directory in sorted((root/'archive').glob('*/*')):
        if not directory.is_dir():continue
        end=latest(directory)
        if end is None:continue
        start=json.loads((directory/'000001.json').read_text())
        verify_snapshot(start)
        if end['revision']<2:raise ValueError('Missing update')
        if not utc(start['as_of_utc'])<utc(end['as_of_utc']):raise ValueError('Nonchronological cutoffs')
        for snap in (start,end):
            if snap['emission_kind']!='pregame' or utc(snap['emitted_at_utc'])>=utc(snap['events'][0]['start_utc']):
                raise ValueError('Emission not actually pregame')
        a=start['events'][0]['forecast']['probabilities'];b=end['events'][0]['forecast']['probabilities']
        rows.append({'sport':end['sport'],'changed':a!=b})
    result={'initial_files_unchanged':len(initial),'event_chains_verified':len(rows),
            'by_sport':dict(Counter(r['sport'] for r in rows)),
            'events_with_changed_probability':sum(r['changed'] for r in rows),
            'all_emissions_pregame':True}
    expected=json.loads((root/'live-verification.json').read_text())
    if any(expected[k]!=v for k,v in result.items()):raise ValueError('Archived verification differs')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',default=str(Path(__file__).parent))
    print(json.dumps(verify(p.parse_args().root)))
