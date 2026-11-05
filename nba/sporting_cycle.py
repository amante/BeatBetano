"""Periodic sporting evidence and observed-minute targets, separate from ML."""
import argparse
import hashlib
import json
import re
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests
from capture_availability import capture as availability_capture
from official_injury_pdf import retrieve as official_report
from player_game_history import parse_boxscore,SUMMARY
from forward_ledger import reconstruct,load_observations,save_new
from forward_capture import DEFAULT_PROTOCOL
from reproducible_slate import digest
from prospective import utc
from sporting_archive import bundles,player_ledger,actual_games


def cycle(protocol,ledger_root,root,run_id,session=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise ValueError('Invalid run ID')
    req=session or requests.Session();now=datetime.now(timezone.utc)
    if now>=utc(protocol['forecast_window_end_exclusive_utc'])+timedelta(days=14):
        return {'status':'collection_window_closed','errors':[]}
    prefix=now.strftime('%Y%m%dT%H%M%S%fZ')+'-'+run_id
    report=reconstruct(load_observations(ledger_root),protocol,now.isoformat())
    root=Path(root);errors=[];captured=None
    future=[]
    for g in report['games']:
        if utc(g['tipoff_utc'])>now and g['source_state']=='pre':
            observed=g.get('source_observed_at_utc')
            if not observed or (now-utc(observed)).total_seconds()>8*3600:
                errors.append({'game_id':g['game_id'],'error_type':'StaleSchedule'});continue
            future.append({k:g[k] for k in ('game_id','home_team','away_team','tipoff_utc')})
    if future:
        cohort={'kind':'nba_sporting_fixture_cohort','created_at_utc':now.isoformat(),'predictions':future}
        cohort['content_sha256']=digest(cohort)
        directory=root/'captures'/prefix
        try:
            captured=availability_capture(cohort,directory)
            errors.extend({'scope':name,**error} for name,error in captured.get('errors',{}).items())
            for filename,key in (('roster.json','errors'),('lineups.json','fetch_errors')):
                provider=json.loads((directory/filename).read_text())
                errors.extend({'scope':filename,**e} for e in provider.get(key,[]))
            save_new(directory/'fixture_cohort.json',cohort)
            try:official=official_report(cohort,session=req)
            except (requests.RequestException,ValueError,ImportError) as exc:
                official={'official_document_retrieved':False,'error_type':type(exc).__name__,
                          'http_status':getattr(getattr(exc,'response',None),'status_code',None),
                          'observed_at_utc':datetime.now(timezone.utc).isoformat()}
            save_new(directory/'official_source.json',official)
            # Original sidecar manifest is preserved; a second manifest covers
            # the cohort reference and official-source result added by this cycle.
            save_new(directory/'cycle_manifest.json',{'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'scope':'availability','error_type':type(exc).__name__,'detail':str(exc)[:300]})
    for game in report['games']:
        if game['status']!='settled_paired_game':continue
        dest=root/'player-games'/(game['game_id']+'.json')
        if dest.exists():continue
        try:
            response=req.get(SUMMARY,params={'event':game['game_id']},timeout=25)
            response.raise_for_status();payload=response.json()
            observed=datetime.now(timezone.utc).isoformat()
            comp=payload['header']['competitions'][0]
            scores={c['team']['abbreviation']:int(c['score']) for c in comp['competitors']}
            if scores!={game['home_team']:game['outcome']['home_points'],game['away_team']:game['outcome']['away_points']}:
                raise ValueError('Final-score disagreement with ledger')
            rows=parse_boxscore(payload,game,observed)
            if {p['team'] for p in rows}!={game['home_team'],game['away_team']}:raise ValueError('Incomplete player teams')
            save_new(dest,{'game':{k:game[k] for k in ('game_id','home_team','away_team','tipoff_utc')},
                           'source':SUMMARY,'observed_at_utc':observed,'players':rows})
            with dest.with_suffix('.json.sha256').open('x') as proof:
                proof.write(hashlib.sha256(dest.read_bytes()).hexdigest())
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            errors.append({'game_id':game['game_id'],'scope':'actual_minutes','error_type':type(exc).__name__,'detail':str(exc)[:300]})
    records,bundle_errors=bundles(root)
    actual=actual_games(root)
    finished=datetime.now(timezone.utc).isoformat()
    targets=player_ledger(records,actual,finished)
    save_new(root/'player-ledgers'/(prefix+'.json'),targets)
    summary={'created_at_utc':finished,'run_id':run_id,'future_games_requested':len(future),
             'sporting_capture':captured,'actual_games_archived':len(actual),
             'player_game_rows':targets['available_player_game_rows'],'errors':errors+bundle_errors,
             'models_modified':False,'probability_adjustment_authorized':False}
    save_new(root/'runs'/(prefix+'.json'),summary)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',default=DEFAULT_PROTOCOL)
    p.add_argument('--ledger-root',default='reports/nba-forward');p.add_argument('--root',default='reports/nba-sporting')
    p.add_argument('--run-id',required=True);a=p.parse_args()
    r=cycle(json.loads(Path(a.protocol).read_text()),a.ledger_root,a.root,a.run_id)
    print(json.dumps(r,indent=2))
    if r['errors']:raise SystemExit('Sporting evidence gaps preserved for review')

if __name__=='__main__':main()
