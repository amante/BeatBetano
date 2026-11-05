"""Immutable NBA observations and first-emission prospective cohort accounting.

No early performance metrics. Missing games, source errors and changed fixture
identities remain visible; final scores never rewrite pregame emissions.
"""
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from prospective import utc
from reproducible_slate import digest


def save_new(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(data,f,indent=2,allow_nan=False)


def parse_schedule(payload,observed_at):
    if not isinstance(payload,dict) or not isinstance(payload.get('events'),list):
        raise ValueError('Missing scoreboard events array')
    if len(payload['events'])>=500:raise ValueError('Potential truncated scoreboard')
    observed=utc(observed_at);rows=[];seen=set()
    for event in payload['events']:
        if event.get('season',{}).get('type')!=2:continue
        comps=event.get('competitions',[])
        if len(comps)!=1:raise ValueError('Unresolved scoreboard competition')
        comp=comps[0];sides={t.get('homeAway'):t for t in comp.get('competitors',[])}
        if set(sides)!={'home','away'}:raise ValueError('Unresolved fixture teams')
        gid=str(event['id']);tip=utc(event['date'])
        if gid in seen:raise ValueError('Duplicate scoreboard ID')
        seen.add(gid)
        home=sides['home']['team']['abbreviation'];away=sides['away']['team']['abbreviation']
        if not home or not away or home==away:raise ValueError('Invalid teams')
        status=comp.get('status',event.get('status',{})).get('type',{})
        completed=status.get('completed') is True
        row={'game_id':gid,'season':int(event['season']['year']),
             'home_team':home,'away_team':away,'tipoff_utc':tip.isoformat(),
             'source_state':status.get('state'),'source_status':status.get('name'),
             'completed':completed,'home_points':None,'away_points':None,
             'observed_at_utc':observed.isoformat()}
        if completed:
            if tip>=observed:raise ValueError('Final score before tipoff')
            hp=int(sides['home']['score']);ap=int(sides['away']['score'])
            if min(hp,ap)<0 or hp==ap:raise ValueError('Invalid NBA final score')
            row.update(home_points=hp,away_points=ap)
        rows.append(row)
    return rows


def in_scope(row,protocol):
    tip=utc(row['tipoff_utc']);scope=protocol['scope']
    return (row['season']==scope['season_end_year']
            and utc(protocol['forecast_window_start_utc'])<=tip<utc(protocol['forecast_window_end_exclusive_utc'])
            and not set(scope['exclude_team_aliases'])&{row['home_team'],row['away_team']})


def verify_observation(obs):
    if digest({k:v for k,v in obs.items() if k!='content_sha256'})!=obs.get('content_sha256'):
        raise ValueError('Observation hash mismatch')
    now=utc(obs['created_at_utc']);seen=set()
    for p in obs['predictions']:
        gid=str(p['game_id'])
        if gid in seen or utc(p['tipoff_utc'])<=utc(p['prediction_as_of_utc']) or utc(p['prediction_as_of_utc'])>now:
            raise ValueError('Duplicate, future or post-start emission')
        seen.add(gid)
        emitted=utc(p['prediction_as_of_utc'])
        if emitted!=now and obs.get('source')=='repository_archive_with_pretip_git_provenance':
            proof=obs.get('provenance',{})
            if not proof.get('git_blob') or not proof.get('file_sha256') or not emitted<=utc(proof['committed_at_utc'])<utc(p['tipoff_utc']):
                raise ValueError('Imported prediction lacks pretip provenance')
        # A collector may compute multiple predictions before sealing; each
        # must have an earlier matching schedule observation, not future evidence.
        if not any(str(r['game_id'])==gid and r['home_team']==p['home_team'] and r['away_team']==p['away_team'] and utc(r['tipoff_utc'])==utc(p['tipoff_utc']) and utc(r['observed_at_utc'])<=emitted for r in obs['schedule']):
            raise ValueError('No timely matching schedule for emission')
        for key in ('elo_p_home','challenger_p_home'):
            x=p[key]
            if type(x) not in (int,float) or not math.isfinite(x) or not 0<x<1:
                raise ValueError('Invalid paired prediction')
    for r in obs['schedule']:
        if utc(r['observed_at_utc'])>now:raise ValueError('Future schedule observation')
    return True


def seal(observation):
    if 'content_sha256' in observation:raise ValueError('Already sealed')
    return {**observation,'content_sha256':digest(observation)}


def reconstruct(observations,protocol,as_of):
    cutoff=utc(as_of);schedules={};predictions={};failures=[];runs=[]
    processed=set()
    for obs in sorted(observations,key=lambda o:(utc(o['created_at_utc']),o['content_sha256'])):
        verify_observation(obs)
        if obs['content_sha256'] in processed:continue
        processed.add(obs['content_sha256'])
        if obs['protocol_sha256']!=digest(protocol):raise ValueError('Protocol mismatch')
        if utc(obs['created_at_utc'])>cutoff:continue
        runs.append(obs['content_sha256'])
        failures.extend({'observation':obs['content_sha256'],**e} for e in obs['source_errors'])
        for r in obs['schedule']:
            schedules.setdefault(str(r['game_id']),[]).append(r)
        for p in obs['predictions']:
            predictions.setdefault(str(p['game_id']),[]).append((p,obs['content_sha256']))
    output=[]
    for gid in sorted(set(schedules)|set(predictions)):
        source=sorted(schedules.get(gid,[]),key=lambda r:utc(r['observed_at_utc']))
        candidate=sorted(predictions.get(gid,[]),key=lambda x:(utc(x[0]['prediction_as_of_utc']),x[1]))
        if not source:raise ValueError('Prediction without eligibility observation')
        # Retain a game that entered scope before a later schedule change too.
        if not any(in_scope(r,protocol) for r in source):continue
        latest=source[-1];first=candidate[0] if candidate else None
        status='awaiting_pregame_capture' if utc(latest['tipoff_utc'])>cutoff else 'missing_pregame_prediction'
        settled=None;issues=[]
        if first:
            p,ref=first
            if not in_scope({**latest,'tipoff_utc':p['tipoff_utc']},protocol):issues.append('prediction_outside_registered_scope')
            for key in ('home_team','away_team','tipoff_utc'):
                if (utc(p[key])!=utc(latest[key]) if key=='tipoff_utc' else p[key]!=latest[key]):issues.append('fixture_'+key+'_changed')
            status='paired_pregame_emission' if not issues else 'fixture_changed_needs_review'
            finals=[r for r in source if r['completed']]
            if finals and not issues:
                finalscores={(r['home_points'],r['away_points']) for r in finals}
                if len(finalscores)>1:
                    issues.append('conflicting_final_scores');status='final_conflict_needs_review'
                else:
                    final=finals[-1]
                    settled={'home_points':final['home_points'],'away_points':final['away_points'],
                             'home_won':int(final['home_points']>final['away_points']),
                             'result_observed_at_utc':final['observed_at_utc']}
                    status='settled_paired_game'
        output.append({'game_id':gid,'home_team':latest['home_team'],'away_team':latest['away_team'],
                       'tipoff_utc':latest['tipoff_utc'],'source_state':latest['source_state'],
                       'source_status':latest['source_status'],'status':status,
                       'first_prediction':first[0] if first else None,
                       'prediction_observation_sha256':first[1] if first else None,
                       'emissions_seen':len(candidate),'outcome':settled,'issues':issues})
    end=utc(protocol['forecast_window_end_exclusive_utc'])
    return {'as_of_utc':cutoff.isoformat(),'protocol_sha256':digest(protocol),'observations':runs,
            'scheduled_games_observed':len(output),'paired_games':sum(g['first_prediction'] is not None for g in output),
            'settled_paired_games':sum(g['status']=='settled_paired_game' for g in output),
            'missing_pregame_games':sum(g['status']=='missing_pregame_prediction' for g in output),
            'source_errors':failures,'games':output,'performance_metrics':None,
            'performance_evaluation_status':'window_open_metrics_withheld' if cutoff<end else 'window_closed_separate_audit_required',
            'automatic_promotion_allowed':False,
            'coverage_limitations':['Single-provider schedule coverage; unseen omissions cannot be certified complete.',
                                    'Cron gaps and source failures remain operational coverage issues.'],
            'no_odds_input':True}


def load_observations(root):
    return [json.loads(p.read_text()) for p in sorted(Path(root).glob('observations/*.json'))]
