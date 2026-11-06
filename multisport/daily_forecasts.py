"""Publish per-event staged forecasts on every daily run; keep prior emissions.

A shared archive is reusable as fixtures start/disappear or new fixtures arrive.
Only sport-model outputs are consumed; no probabilities or injury effects are fitted.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from multisport.contract import utc
from multisport.data_lineage import digest
from multisport.forecast_revisions import snapshot, save_snapshot, verify_snapshot
from multisport.sport_adapters import adapt


def _directory(root,sport,event_id):
    # Hash arbitrary provider IDs instead of treating IDs as filesystem paths.
    return Path(root)/sport/digest(str(event_id))


def latest(directory):
    previous=None
    for n,path in enumerate(sorted(Path(directory).glob('*.json')),1):
        report=json.loads(path.read_text())
        verify_snapshot(report)
        if report['revision']!=n or report['parent_snapshot_sha256']!=(previous['content_sha256'] if previous else None):
            raise ValueError('Broken forecast revision chain')
        previous=report
    return previous


def publish(sport,source,archive,revision='unrecorded',final_window_minutes=30,live_only=False):
    if type(final_window_minutes) is not int or not 0<=final_window_minutes<=180:
        raise ValueError('Invalid final pregame window')
    Path(archive).mkdir(parents=True,exist_ok=True)
    report=adapt(sport,source,revision)
    outputs=[]
    for event in report['events']:
        if live_only and datetime.now(timezone.utc)>=utc(event['start_utc']):
            outputs.append({'event_id':event['event_id'],'status':'event_started'})
            continue
        folder=_directory(archive,sport,event['event_id'])
        prior=latest(folder)
        # An absent source forecast never destroys a previously recorded forecast.
        if event['forecast'] is None:
            outputs.append({'event_id':event['event_id'],'status':'no_source_probability',
                            'latest_snapshot_sha256':prior['content_sha256'] if prior else None})
            continue
        minutes=(utc(event['start_utc'])-utc(report['as_of_utc'])).total_seconds()/60
        stage='final_pregame' if minutes<=final_window_minutes else 'update' if prior else 'initial'
        if prior and prior['events'][0]['forecast']['stage']=='final_pregame':
            stage='final_pregame'
        single={**copy.deepcopy(report),'events':[copy.deepcopy(event)]}
        single['events'][0]['forecast']['stage']=stage
        single['source_output_sha256']=digest(source)
        single['source_model_output']=copy.deepcopy(source_event(sport,source,event['event_id']))
        if prior and utc(prior['as_of_utc'])==utc(report['as_of_utc']):
            if prior['source_output_sha256']!=single['source_output_sha256']:
                raise ValueError('Changed output with identical source cutoff')
            outputs.append({'event_id':event['event_id'],'status':'reused',
                            'snapshot_sha256':prior['content_sha256'],'stage':prior['events'][0]['forecast']['stage']})
            continue
        frozen=snapshot(single,prior)
        if live_only and frozen['emission_kind']!='pregame':
            outputs.append({'event_id':event['event_id'],'status':'event_started'})
            continue
        path=folder/(str(frozen['revision']).zfill(6)+'.json')
        save_snapshot(path,frozen)
        outputs.append({'event_id':event['event_id'],'status':'published','stage':stage,
                        'revision':frozen['revision'],'snapshot_sha256':frozen['content_sha256'],
                        'snapshot_path':str(path),'emission_kind':frozen['emission_kind']})
    return {'sport':sport,'as_of_utc':report['as_of_utc'],'events':outputs,
            'forecast_publication_only':True,'selection_approval_changed':False}


def source_event(sport,source,event_id):
    rows=source.get('predictions') if sport=='nba' else source.get('games',source.get('events')) if sport=='nhl' else source.get('events')
    return next(r for r in rows if str(r.get('event_id') or r.get('game_id'))==event_id)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sport',required=True)
    p.add_argument('--input',required=True)
    p.add_argument('--archive',required=True)
    p.add_argument('--revision',default='unrecorded')
    p.add_argument('--final-window-minutes',type=int,default=30)
    p.add_argument('--summary',required=True)
    a=p.parse_args()
    result=publish(a.sport,json.loads(Path(a.input).read_text()),a.archive,a.revision,a.final_window_minutes,live_only=True)
    path=Path(a.summary);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps({'sport':a.sport,'events':len(result['events'])}))


if __name__=='__main__':main()
