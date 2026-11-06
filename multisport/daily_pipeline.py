"""Daily five-sport forecast runner; isolate source failures and retain revisions."""
import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from multisport.contract import SPORTS, utc
from multisport.daily_forecasts import publish
from multisport.data_lineage import digest

ROOT=Path(__file__).resolve().parents[1]


def soccer_source(games,as_of,cache):
    from soccer.data import load_history
    from soccer.poisson import fit,predict
    rows,manifest=load_history(ROOT/'reports/soccer/base-2026-11-02/history')
    policy=json.loads((ROOT/'reports/soccer/base-2026-11-02/backtest.json').read_text())
    penalty=policy['selected_penalty']
    key=digest({'manifest':manifest,'penalty':penalty,
                'model_code':(ROOT/'soccer/poisson.py').read_text()})
    path=Path(cache)/('soccer-model-'+key+'.json')
    if path.exists():model=json.loads(path.read_text())
    else:
        model=fit(rows,penalty)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f:json.dump(model,f)
    def canonical(name):
        # Exact presentation suffix normalization only; no fuzzy team matching.
        return name.removesuffix(' FC').removesuffix(' AFC').removeprefix('AFC ')
    lookup={}
    for name in model['teams']:lookup.setdefault(canonical(name),[]).append(name)
    events=[]
    for game in games:
        e={'event_id':game['id'],'home':game['home'],'away':game['away'],'start_utc':game['start_utc'],
           'model_version':'soccer-existing-poisson-'+key[:12],
           'assumptions':['Existing Premier League season-frozen Poisson model; no current lineup adjustment.'],
           'unresolved_inputs':['Confirmed lineup and current availability']}
        names=[lookup.get(canonical(game[side]),[]) for side in ('home','away')]
        if game.get('league')=='Premier League' and all(len(v)==1 for v in names):
            e['probabilities']=predict(model,names[0][0],names[1][0],utc(game['start_utc']).date().isoformat())['probabilities']
        else:e['missing_baseline_reason']='No supported league model or unique historical team mapping'
        events.append(e)
    return {'as_of_utc':as_of,'events':events,'odds_used_in_sport_model':False}


def generate_source(sport,games,as_of,workdir,archive):
    workdir=Path(workdir);workdir.mkdir(parents=True,exist_ok=True)
    if sport=='soccer':return soccer_source(games,as_of,workdir/'cache')
    if sport=='tennis':
        return {'as_of_utc':as_of,'odds_used_in_sport_model':False,'events':[
            {'event_id':g['id'],'start_utc':g['start_utc'],'home':g['home'],'away':g['away'],
             'missing_baseline_reason':'No implemented tennis probability model'} for g in games]}
    # Keep legacy sport import paths isolated by invoking their real daily entrypoints.
    outputs=[]
    days=sorted({utc(g['start_utc']).astimezone(ZoneInfo('America/New_York')).date().isoformat() for g in games})
    history=None
    if sport=='nba':
        sys.path.insert(0,str(ROOT/'nba'))
        from history_store import daily_delta
        raw=ROOT/'reports/nba-2026-11-04/history.json'
        import hashlib
        manifest=json.loads(raw.with_name('manifest.json').read_text())
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=manifest['files']['history.json']:
            raise ValueError('Historical NBA ledger digest mismatch')
        history_rows=json.loads(raw.read_text())
        from datetime import timedelta
        start=max(utc(g['tipoff_utc']).date() for g in history_rows)
        end=utc(as_of).date()-timedelta(days=1)
        delta,_=daily_delta(workdir/'cache/nba-deltas',start.isoformat(),end.isoformat()) if start<=end else ([],{})
        merged={str(g['game_id']):g for g in history_rows}
        for g in delta:
            if str(g['game_id']) in merged and merged[str(g['game_id'])]!=g:
                raise ValueError('Conflicting NBA result in daily delta')
            merged[str(g['game_id'])]=g
        history=workdir/'nba-history.json';history.write_text(json.dumps(list(merged.values())))
    elif sport=='nfl':
        import requests
        NFL_URL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
        history=workdir/'cache'/('nfl-'+utc(as_of).date().isoformat()+'.csv')
        if not history.exists():
            response=requests.get(NFL_URL,timeout=40);response.raise_for_status()
            if not {'home_team','away_team','season','gameday'}<=set(next(csv.reader(io.StringIO(response.text)))):
                raise ValueError('Unexpected NFL history schema')
            history.parent.mkdir(parents=True,exist_ok=True)
            with history.open('x') as f:f.write(response.text)
    for day in days:
        output=workdir/(sport+'-'+day+'-'+digest(as_of)[:12]+'.json')
        script={'nba':'nba/daily_pipeline.py','nfl':'nfl/nfl_hoy.py','nhl':'nhl/nhl_hoy.py'}[sport]
        command=[sys.executable,str(ROOT/script),'--date',day,'--output',str(output),'--forecast-archive',str(archive)]
        if history is not None:command+=['--history',str(history)]
        if sport=='nba':command+=['--allow-empty']
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=180)
        if done.returncode:raise ValueError(sport+' source generation failed: '+done.stderr[-800:])
        if output.exists():outputs.append(json.loads(output.read_text()))
    # Each real CLI already emits its own dated snapshots; return its raw output
    # for status accounting, not to assert a new common source observation time.
    return outputs


def coverage_bindings(sport, games, sources, publications):
    """Bind provider-specific event IDs by audited teams and exact start time."""
    available={e['event_id'] for p in publications for e in p['events']
               if e['status'] in ('published','reused')}
    bindings=[]
    if sport=='nhl':
        from nhl.pulso_goalie_multisource_257 import TEAM_NAMES
        import unicodedata
        def normalized(value):
            text=unicodedata.normalize('NFKD',value).casefold().replace('.','')
            return " ".join(''.join(c for c in text if not unicodedata.combining(c)).split())
        names={normalized(name):code for code,name in TEAM_NAMES.items()}
        def team_code(value):return names.get(normalized(value))
        identities={}
        for source in sources:
            for row in source.get('events',source.get('games',[])):
                sid=str(row.get('event_id') or row.get('game_id'))
                identity=(row.get('home_team') or row.get('home'),row.get('away_team') or row.get('away'),
                          utc(row['start_utc']))
                identities.setdefault(sid,set()).add(identity)
        for game in games:
            requested=(team_code(game['home']),team_code(game['away']),utc(game['start_utc']))
            matches=[sid for sid,values in identities.items()
                     if requested[0] and requested[1] and values=={requested}]
            if len(matches)==1:
                bindings.append({'fixture_id':str(game['id']),'forecast_event_id':matches[0],
                                 'method':'explicit_team_name_crosswalk_and_exact_start',
                                 'forecast_available':matches[0] in available})
    else:
        # These adapters use the same ESPN/provider fixture IDs as the collector.
        for game in games:
            gid=str(game['id'])
            bindings.append({'fixture_id':gid,'forecast_event_id':gid,
                             'method':'same_provider_event_id','forecast_available':gid in available})
    matched={b['fixture_id'] for b in bindings if b['forecast_available']}
    return bindings,sorted({str(g['id']) for g in games}-matched)


def run(feed,archive,workdir,provider=generate_source):
    Path(archive).mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    # Latest runtime, not the collector's earlier clock, decides remaining fixtures.
    active=[g for g in feed['games'] if not g.get('completed') and utc(g['start_utc'])>utc(now)
            and g.get('status') in ('STATUS_SCHEDULED','scheduled')]
    report={'as_of_utc':now,'sports':{},'errors':[],'selection_approval_changed':False}
    for sport in SPORTS:
        sport_now=datetime.now(timezone.utc).isoformat()
        games=[g for g in active if g['sport']==sport and utc(g['start_utc'])>utc(sport_now)]
        if not games:
            report['sports'][sport]={'status':'no_pending_fixtures','events':[]};continue
        try:
            sources=provider(sport,games,sport_now,workdir,archive)
            if isinstance(sources,dict):sources=[sources]
            publications=[publish(sport,s,archive,revision='daily-'+sport,live_only=True) for s in sources]
            integration = []
            if sport == 'nba':
                seals = {s.get('content_sha256') for s in sources if s.get('content_sha256')}
                for path in Path(workdir).glob('nba-*.integration.json'):
                    diagnostic = json.loads(path.read_text())
                    if diagnostic.get('baseline_snapshot_sha256') in seals:
                        integration.append(diagnostic)
            bindings,missing=coverage_bindings(sport,games,sources,publications)
            report['sports'][sport]={'status':'processed' if not missing else 'partial_forecast_coverage',
                                    'publications':publications,'fixtures_requested':len(games),
                                    'fixtures_with_forecast':len(games)-len(missing),'fixture_bindings':bindings,
                                    'missing_baseline_fixture_ids':missing}
            if sport == 'nba':report['sports'][sport]['sporting_integration']=integration
        except Exception as exc:
            # A failed sport must not suppress another sport's baseline or erase its archive.
            error={'sport':sport,'type':type(exc).__name__,'detail':str(exc)[:1200]}
            report['errors'].append(error)
            report['sports'][sport]={'status':'source_error','fixtures_requested':len(games),'error':error}
    report['status']='partial_source_failure' if report['errors'] else 'partial_forecast_coverage' if any(v['status']=='partial_forecast_coverage' for v in report['sports'].values()) else 'completed'
    return report


def main():
    p=argparse.ArgumentParser()
    for key in ('fixtures','archive','workdir','summary'):p.add_argument('--'+key,required=True)
    a=p.parse_args()
    report=run(json.loads(Path(a.fixtures).read_text()),a.archive,a.workdir)
    output=Path(a.summary);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps({'status':report['status'],'sports':{k:v['status'] for k,v in report['sports'].items()}}))


if __name__=='__main__':main()
