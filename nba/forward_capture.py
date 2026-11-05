"""Scheduled collection for the frozen NBA forward protocol; no odds or tuning."""
import argparse
import hashlib
import json
import re
from datetime import datetime,timedelta,timezone,date
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from espn_games import BASE,parse_events
from model import evaluate
from challenger import predict_challenger
from clean_regular import clean
from forward_ledger import parse_schedule,in_scope,seal,save_new,reconstruct,load_observations
from reproducible_slate import digest
from prospective import utc

DEFAULT_PROTOCOL='reports/nba-validation-2026-11-04/prospective_protocol.json'
BASE_HISTORY='reports/nba-2026-11-04/history.json'
GAME_FIELDS=('game_id','season','tipoff_utc','home_team','away_team','home_points','away_points')


def verify_sources(protocol,root=Path('.')):
    for name,expected in protocol['locked_model_source_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise ValueError('Frozen model source changed: '+name)


def paired(history,fixtures,created,clock=None):
    now=utc(created)
    if any(utc(g['tipoff_utc'])>=now or g['home_points'] is None or g['away_points'] is None for g in history):
        raise ValueError('Future or unfinished training data')
    output=[]
    for fixture in fixtures:
        if utc(fixture['tipoff_utc'])<=now:continue
        one={k:fixture[k] for k in GAME_FIELDS}
        one.update(home_points=None,away_points=None)
        rows=sorted(history+[one],key=lambda g:(utc(g['tipoff_utc']),str(g['game_id'])))
        base=list(evaluate(rows,season_min=2024,season_max=2027))[-1]
        challenger=predict_challenger(rows)[-1]
        emitted=(clock() if clock else datetime.now(timezone.utc)).isoformat()
        if utc(one['tipoff_utc'])<=utc(emitted):continue
        output.append({k:one[k] for k in ('game_id','home_team','away_team','tipoff_utc')}|
                      {'prediction_as_of_utc':emitted,'elo_p_home':base.p_home,'challenger_p_home':challenger['p_home']})
    return output


def capture(protocol,root,run_id,session=None):
    verify_sources(protocol)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise ValueError('Invalid run ID')
    request=session or requests.Session();started=datetime.now(timezone.utc)
    if started>=utc(protocol['forecast_window_end_exclusive_utc'])+timedelta(days=14):
        report=reconstruct(load_observations(root),protocol,started.isoformat())
        report['current_source_error_count']=0
        return report
    day=started.astimezone(ZoneInfo('America/New_York')).date()
    schedule=[];errors=[];current={};coverage=[]
    # Full current-season reconstruction avoids silently skipping dates after
    # an outage; the prior three complete seasons remain pinned in the repo.
    cursor=date(2026,10,20)
    while cursor<=day+timedelta(days=1):
        stamp=datetime.now(timezone.utc).isoformat()
        try:
            response=request.get(BASE,params={'dates':cursor.strftime('%Y%m%d'),'limit':500,'seasontype':2},timeout=25)
            response.raise_for_status();payload=response.json()
            observed=datetime.now(timezone.utc).isoformat()
            rows=parse_schedule(payload,observed)
            coverage.append({'league_date':cursor.isoformat(),'observed_at_utc':observed,'events':len(rows)})
            for r in rows:
                if r['season']==2027 and r['completed']:
                    value={k:r[k] for k in GAME_FIELDS}
                    if r['game_id'] in current and current[r['game_id']]!=value:raise ValueError('Conflicting historical game')
                    current[r['game_id']]=value
                if in_scope(r,protocol):schedule.append(r)
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            errors.append({'league_date':cursor.isoformat(),'observed_at_utc':stamp,'error_type':type(exc).__name__,'detail':str(exc)[:300]})
        cursor+=timedelta(days=1)
    # Resolve repeated scoreboard rows by ID before forecasting. Conflicting
    # schedule identities are retained for review and block this run's forecasts.
    unique={}
    for row in schedule:
        old=unique.get(row['game_id'])
        if old and any(old[k]!=row[k] for k in ('home_team','away_team','tipoff_utc')):
            errors.append({'game_id':row['game_id'],'error_type':'ConflictingSchedule','detail':'Identity or tipoff differs across source dates'})
        unique[row['game_id']]=row
    archived=json.loads(Path(BASE_HISTORY).read_text())
    past,audit=clean([g for g in archived if g['season'] in (2024,2025,2026)])
    if not audit['coverage_verified'] or len(past)!=3690:raise ValueError('Pinned history coverage invalid')
    created=datetime.now(timezone.utc).isoformat()
    # A whole-day source failure may omit training results, so no new forecast
    # is emitted from a known incomplete history; eligibility is still retained.
    existing=load_observations(root)
    already_emitted={p['game_id'] for o in existing for p in o['predictions']}
    fixtures=[r for r in unique.values() if r['game_id'] not in already_emitted and r['source_state']=='pre' and not r['completed'] and utc(r['tipoff_utc'])>utc(created)]
    history=sorted(past+list(current.values()),key=lambda g:(utc(g['tipoff_utc']),str(g['game_id'])))
    forecasts=paired(history,fixtures,created) if not errors else []
    created=datetime.now(timezone.utc).isoformat()
    obs=seal({'schema_version':1,'created_at_utc':created,'run_id':run_id,
              'protocol_sha256':digest(protocol),'source':BASE,'source_day_coverage':coverage,
              'source_errors':errors,'schedule':schedule,'predictions':forecasts,
              'history_sha256':digest(history),'pinned_history_sha256':digest(past),
              'current_season_history':list(current.values()),'no_odds_input':True})
    filename=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+run_id+'.json'
    save_new(Path(root)/'observations'/filename,obs)
    report=reconstruct(load_observations(root),protocol,created)
    report['current_source_error_count']=len(errors)
    save_new(Path(root)/'runs'/filename,report)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',default=DEFAULT_PROTOCOL)
    p.add_argument('--root',default='reports/nba-forward');p.add_argument('--run-id',required=True)
    a=p.parse_args();r=capture(json.loads(Path(a.protocol).read_text()),a.root,a.run_id)
    print(json.dumps({k:r[k] for k in ('as_of_utc','scheduled_games_observed','paired_games','settled_paired_games','missing_pregame_games','performance_evaluation_status')},indent=2))
    if r['current_source_error_count']:raise SystemExit('Source failures preserved; inspect observation and cohort coverage')

if __name__=='__main__':main()
