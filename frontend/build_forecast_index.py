"""Build a small public dashboard index from sealed per-event forecast chains."""
import argparse
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisport.forecast_revisions import verify_snapshot
from multisport.contract import SPORTS,utc


def build(archive):
    root=Path(archive)
    events=[];errors=[]
    for folder in sorted(root.glob('*/*')):
        if not folder.is_dir():continue
        try:
            previous=None;history=[];identity=None
            paths=sorted(folder.glob('*.json'))
            for n,path in enumerate(paths,1):
                snap=json.loads(path.read_text());verify_snapshot(snap)
                if snap['sport'] not in SPORTS or folder.parent.name!=snap['sport']:
                    raise ValueError('Sport identity mismatch')
                if len(snap['events'])!=1:raise ValueError('Per-event snapshot required')
                game=snap['events'][0]
                current=(snap['sport'],game['event_id'],game['participants'])
                if identity is not None and current!=identity:raise ValueError('Fixture identity changed')
                identity=current
                if snap['revision']!=n or snap['parent_snapshot_sha256']!=(previous['content_sha256'] if previous else None):
                    raise ValueError('Broken revision chain')
                if snap['emission_kind']!='pregame' or not utc(snap['as_of_utc'])<=utc(snap['emitted_at_utc'])<utc(game['start_utc']):
                    raise ValueError('Not an actual pregame emission')
                if previous and utc(snap['as_of_utc'])<=utc(previous['as_of_utc']):
                    raise ValueError('Nonchronological source cutoff')
                if game.get('forecast') is None:raise ValueError('Missing forecast')
                history.append({'revision':n,'snapshot_sha256':snap['content_sha256'],
                                'cutoff_utc':snap['as_of_utc'],'emitted_at_utc':snap['emitted_at_utc'],
                                'start_utc':game['start_utc'],**game['forecast']})
                previous=snap
            if not history:continue
            first,last=history[0],history[-1]
            events.append({'sport':identity[0],'event_id':identity[1],'participants':identity[2],
                           'start_utc':last['start_utc'],'initial':first,'latest':last,'history':history,
                           'delta':{k:last['probabilities'][k]-first['probabilities'][k] for k in first['probabilities']},
                           'selection_status':'PASS','calibration_certified':False})
        except (ValueError,KeyError,TypeError,OSError) as exc:
            errors.append({'sport':folder.parent.name,'archive_key':folder.name,'reason':str(exc)})
    events.sort(key=lambda x:(x['start_utc'],x['sport'],x['event_id']))
    return {'schema_version':1,'kind':'progressive_forecast_index','generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'events':events,'errors':errors,'archive_present':root.is_dir(),
            'note':'Publication history, not certified selections or a performance evaluation.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive',default='frontend/data/forecast_archive')
    p.add_argument('--output',default='frontend/data/forecast-index.json')
    a=p.parse_args();data=build(a.archive)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps({'events':len(data['events']),'errors':len(data['errors'])}))


if __name__=='__main__':main()
