"""Read timestamped sporting sidecars; no availability is inferred from silence."""
import hashlib
import json
from pathlib import Path
from prospective import utc

LEGACY=Path('reports/nba-availability-2026-11-04-2147')


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
            errors.extend({'path':str(folder),'scope':name,**error} for name,error in summary.get('errors',{}).items())
            good.append({'ref':str(folder),'availability':json.loads((folder/'availability.json').read_text()),
                         'lineups':json.loads((folder/'lineups.json').read_text())})
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
