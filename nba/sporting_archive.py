"""Read timestamped sporting sidecars; no availability is inferred from silence."""
import hashlib
import json
from pathlib import Path
from datetime import datetime,time,timezone
from prospective import utc

LEGACY=Path('reports/nba-availability-2026-11-04-2147')
OFFICIAL_REPORT_RELEASE_UTC=time(10,30)

def official_report_module_state(summary,error=None):
    if summary.get('official_injury_report_retrieved') is True:
        return {'status':'available','entered_prediction':False,
                'detail':'Fuente capturada; el modelo actual no aplica ajuste de lesiones.'}
    if error is None and not summary.get('errors',{}).get('official_injury_report'):
        return {'status':'not_observed','entered_prediction':False,
                'detail':'No hay captura de la fuente oficial en este paquete.'}
    captured=summary.get('captured_at_utc')
    try:
        at=datetime.fromisoformat(str(captured).replace('Z','+00:00'))
        if at.tzinfo is None:raise ValueError('Capture timestamp must include timezone')
        release=datetime.combine(at.date(),OFFICIAL_REPORT_RELEASE_UTC,tzinfo=timezone.utc)
    except (TypeError,ValueError):
        return {'status':'failed','entered_prediction':False,
                'detail':'No se pudo validar la hora de captura de la fuente oficial.'}
    if at.astimezone(timezone.utc)<release:
        return {'status':'pending','entered_prediction':False,
                'detail':'Captura anterior a las 10:30 UTC; el informe aún puede no estar publicado.'}
    detail=(error or summary.get('errors',{}).get('official_injury_report') or {}).get('detail','Fuente oficial no disponible tras la hora de publicación esperada.')
    return {'status':'failed','entered_prediction':False,'detail':str(detail)[:500]}


def bundles(root):
    folders=sorted((Path(root)/'captures').glob('*'))
    if LEGACY.is_dir():folders=[LEGACY]+folders
    good=[];errors=[]
    for folder in folders:
        try:
            manifest=json.loads((folder/'manifest.json').read_text())
            for name,expected in manifest['files'].items():
                if Path(name).name!=name:raise ValueError('Invalid manifest path')
                if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected:raise ValueError('Manifest mismatch')
            summary=json.loads((folder/'summary.json').read_text()) if (folder/'summary.json').is_file() else {}
            source_errors=summary.get('errors',{})
            official_error=source_errors.get('official_injury_report')
            module_status={**official_report_module_state(summary,official_error),
                           'captured_at_utc':summary.get('captured_at_utc')}
            for name,error in source_errors.items():
                if name=='official_injury_report' and module_status['status']=='pending':
                    continue
                errors.append({'path':str(folder),'scope':name,**error})
            good.append({'ref':str(folder),'availability':json.loads((folder/'availability.json').read_text()),
                         'lineups':json.loads((folder/'lineups.json').read_text()),
                         'module_statuses':{'official_injury_report':module_status}})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'path':str(folder),'error_type':type(exc).__name__})
    return good,errors


def team_observation(records,gid,team,tip,as_of):
    selected=[]
    for bundle in records:
        a=bundle['availability'].get('games',{}).get(str(gid),{}).get('teams',{}).get(team,{})
        when=a.get('observed_at_utc')
        try:timely=bool(when and utc(when)<utc(tip) and utc(when)<=utc(as_of))
        except (ValueError,TypeError):timely=False
        if timely and a.get('roster_complete'):
            selected.append((utc(when),bundle,a))
    if not selected:return None
    _,bundle,a=max(selected,key=lambda item:(item[0],item[1]['ref']))
    lineup=bundle['lineups'].get('games',{}).get(str(gid),{}).get('teams',{}).get(team,{})
    try:lineup_ok=bool(lineup.get('observed_at_utc') and utc(lineup['observed_at_utc'])<utc(tip) and utc(lineup['observed_at_utc'])<=utc(as_of))
    except (ValueError,TypeError):lineup_ok=False
    return {'observed_at_utc':a['observed_at_utc'],'source_ref':bundle['ref'],
            'source_url':a.get('roster_source'),'roster_complete':a['roster_complete'],
            'allocation_ready':a.get('allocation_ready') is True,
            'players':[{'player_id':p['player_id'],'player':p['player'],'status':p['status'],
                        'status_sources':p.get('status_sources',[])} for p in a['players']],
            'provider_starters':lineup.get('starters',[]) if lineup_ok else [],
            'lineup_status':lineup.get('lineup_status','unavailable') if lineup_ok else 'unavailable',
            'official_injury_status_verified':False,'probabilities_adjusted':False}


def player_ledger(records,observed_games,as_of):
    rows=[];seen_games=set()
    for observed in observed_games:
        game=observed['game'];gid=str(game['game_id']);tip=game['tipoff_utc']
        if gid in seen_games:raise ValueError('Duplicate actual game')
        seen_games.add(gid)
        if utc(observed['observed_at_utc'])>utc(as_of):continue
        if utc(observed['observed_at_utc'])<=utc(tip):raise ValueError('Actual minutes observed before game')
        seen=set()
        for player in observed['players']:
            key=(player['team'],player['player_id'])
            if key in seen:raise ValueError('Duplicate actual player row')
            seen.add(key)
            team=team_observation(records,gid,player['team'],tip,as_of)
            claim=next((p for p in team['players'] if p['player_id']==player['player_id']),None) if team else None
            actual=player['minutes_played']
            rows.append({'game_id':gid,'team':player['team'],'player_id':player['player_id'],'player':player['player'],
                         'tipoff_utc':tip,'pregame_status':claim['status'] if claim else 'unknown',
                         'pregame_observed_at_utc':team['observed_at_utc'] if team else None,
                         'pregame_source_ref':team['source_ref'] if team else None,
                         'minutes_actual':actual,'did_not_play':player['did_not_play'],
                         'outcome_observed_at_utc':observed['observed_at_utc'],
                         'starter_reported_postgame':player.get('starter_reported_postgame'),
                         'fit_for_availability_impact':False,
                         'status':'observed_minutes_with_pretip_context' if claim and type(actual) in (int,float) else 'missing_pretip_context_or_minutes'})
    return {'schema_version':1,'created_at_utc':as_of,'rows':rows,
            'available_player_game_rows':len(rows),'fit_for_validated_impact_training':False,
            'note':'Postgame minutes are targets only; DNP is not proof of a pregame injury. Supplementary statuses are not independently verified active/out history.'}


def actual_games(root):
    result=[]
    for path in sorted((Path(root)/'player-games').glob('*.json')):
        expected=path.with_suffix('.json.sha256').read_text().strip()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Actual player target integrity mismatch')
        result.append(json.loads(path.read_text()))
    return result
