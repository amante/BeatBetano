"""Shared forecast stages and immutable revisions; sport models supply probabilities.

Forecast publication does not certify calibration or authorize a selection.
Missing confirmed starters or unresolved availability never alone block a forecast.
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from multisport.contract import SPORTS, probability, utc
from multisport.data_lineage import digest

STAGES=('initial','update','final_pregame')


def validate_forecast(forecast, sport):
    if sport not in SPORTS:
        raise ValueError('Unsupported sport')
    if forecast.get('stage') not in STAGES:
        raise ValueError('Unknown forecast stage')
    if not isinstance(forecast.get('model_version'),str) or not forecast['model_version'].strip():
        raise ValueError('Forecast model version required')
    values=forecast.get('probabilities')
    keys={'home','draw','away'} if sport=='soccer' else {'home','away'}
    if not isinstance(values,dict) or set(values)!=keys:
        raise ValueError('Forecast outcome definitions differ from sport')
    if not all(probability(v) for v in values.values()) or abs(sum(values.values())-1)>1e-6:
        raise ValueError('Forecast probabilities must be finite and sum to one')
    for field in ('assumptions','unresolved_inputs'):
        items=forecast.get(field)
        if not isinstance(items,list) or any(not isinstance(x,str) or not x.strip() for x in items):
            raise ValueError('Forecast '+field+' must be explicit text lists')
    if forecast['unresolved_inputs'] and not forecast['assumptions']:
        raise ValueError('Unresolved inputs require declared assumptions')
    if forecast.get('selection_status')!='PASS' or forecast.get('calibration_certified') is not False:
        raise ValueError('Forecast stages cannot certify or approve selections')
    return True


def make_forecast(sport, probabilities, model_version, stage='initial', assumptions=(), unresolved_inputs=()):
    result={'stage':stage,'probabilities':copy.deepcopy(probabilities),
            'model_version':model_version,'assumptions':list(assumptions),
            'unresolved_inputs':list(unresolved_inputs),'selection_status':'PASS',
            'calibration_certified':False}
    validate_forecast(result,sport)
    return result


def verify_snapshot(report):
    body={k:v for k,v in report.items() if k!='content_sha256'}
    if report.get('content_sha256')!=digest(body):
        raise ValueError('Forecast snapshot digest mismatch')
    lineage=report.get('model_provenance')
    if lineage is not None:
        if not isinstance(lineage,dict):
            raise ValueError('Model provenance must be an object')
        for key in ('training_data_sha256','predictor_input_sha256','schedule_input_sha256',
                    'training_manifest_sha256','source_output_sha256','model_code_sha256'):
            value=lineage.get(key)
            if value is not None and (not isinstance(value,str) or len(value)!=64 or
                    any(ch not in '0123456789abcdef' for ch in value)):
                raise ValueError('Invalid model provenance digest')
        for key in ('training_cutoff_utc','predictor_input_as_of_utc'):
            value=lineage.get(key)
            if value is not None and utc(value)>utc(report['as_of_utc']):
                raise ValueError('Model provenance cutoff is after forecast cutoff')
        revision=lineage.get('model_code_revision')
        if revision is not None and (not isinstance(revision,str) or
                len(revision)<7 or len(revision)>40 or
                any(ch not in '0123456789abcdef' for ch in revision)):
            raise ValueError('Invalid model code revision')
    from multisport.contract import validate_report
    validate_report(report)


def snapshot(report, previous=None):
    """Seal the entire slate with source cutoff and a distinct actual emission time."""
    from multisport.contract import validate_report
    validate_report(report)
    result=copy.deepcopy(report)
    for key in ('content_sha256','revision','parent_snapshot_sha256','changes','emitted_at_utc','emission_kind'):
        result.pop(key,None)
    changes=[]
    if previous is not None:
        verify_snapshot(previous)
        if previous['sport']!=report['sport'] or utc(report['as_of_utc'])<=utc(previous['as_of_utc']):
            raise ValueError('Revision must follow previous cutoff for the same sport')
        before={g['event_id']:g for g in previous['events']}
        after={g['event_id']:g for g in report['events']}
        if set(before)!=set(after):
            raise ValueError('Revision must retain the same fixture cohort')
        for gid,game in after.items():
            old=before[gid]
            if old['participants']!=game['participants']:
                raise ValueError('Revision participant identity mismatch')
            old_f,new_f=old.get('forecast'),game.get('forecast')
            if old_f and new_f and STAGES.index(new_f['stage'])<STAGES.index(old_f['stage']):
                raise ValueError('Forecast stage cannot move backwards')
            changes.append({'event_id':gid,'before':old_f,'after':new_f,
                            'previous_start_utc':old['start_utc'],'start_utc':game['start_utc']})
    now=datetime.now(timezone.utc)
    if utc(result['as_of_utc'])>now:
        raise ValueError('Forecast cutoff cannot be in the future')
    result.update(revision=previous['revision']+1 if previous else 1,
                  parent_snapshot_sha256=previous['content_sha256'] if previous else None,
                  changes=changes,emitted_at_utc=now.isoformat(),
                  emission_kind='pregame' if all(now<utc(g['start_utc']) for g in result['events']) else 'retrospective_replay')
    result['content_sha256']=digest(result)
    return result


def save_snapshot(path, report):
    verify_snapshot(report)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        json.dump(report,f,indent=2,allow_nan=False)
