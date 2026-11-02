"""Emission-matched prospective goalie cohort and manual, date-frozen research evaluation."""
import argparse
from collections import defaultdict
from datetime import date
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import re
from zoneinfo import ZoneInfo
from nhl.pulso_pregame_v7 import parse_utc
from nhl.pulso_collective_audit_208 import freeze_prediction, quantile
from nhl.pulso_outcome_forecast_218 import VERSION
from nhl.pulso_goalie_model_269 import train, predict, logit, score


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def cohort(repository, run_id=None):
    if run_id is not None and not str(run_id).isdigit():raise ValueError('Numeric run ID required')
    root=Path(repository); candidates=defaultdict(list); rejected=[]
    labels={}
    for path in sorted((root/'frontend/data/nhl-postmortems').glob('*.json')):
        report=json.loads(path.read_text())
        # Public reports are pointers to content-addressed official audits.
        if report.get('kind')!='nhl_daily_postmortem':raise ValueError('Unexpected results report')
        core={k:v for k,v in report.items() if k not in ('revision_sha256','generated_at_utc','archive_path')}
        sha=hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        if sha!=report.get('revision_sha256'):raise ValueError('Postmortem hash mismatch')
        for g in report['games']:
            if g.get('state') not in ('OFF','FINAL') or not g.get('outcomes'):continue
            y=g['outcomes'].get('ml_winner')
            if y not in ('home','away'):raise ValueError('Invalid official ML outcome')
            gid=str(g['game_id'])
            if gid in labels:raise ValueError('Duplicate official result')
            labels[gid]=(g,y,sha,report['generated_at_utc'])
    paths=(root/'nhl/learning/pregame').glob('run-'+str(run_id)+'.json' if run_id is not None else 'run-*.json')
    for path in sorted(paths):
        run=path.stem.removeprefix('run-') if hasattr(str,'removeprefix') else path.stem[4:]
        try:
            if not run.isdigit():raise ValueError('Invalid run ID')
            evidence=json.loads(path.read_text())
            if evidence.get('kind')!='nhl_pregame_player_evidence_v1' or evidence.get('run_id')!=run:raise ValueError('Invalid evidence identity')
            if digest({k:v for k,v in evidence.items() if k!='content_sha256'})!=evidence.get('content_sha256'):raise ValueError('Evidence hash mismatch')
            bundle=json.loads(gzip.decompress(path.with_suffix('.sources.json.gz').read_bytes()))
            hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in bundle.items()}
            if hashes!=evidence['source_files_sha256']:raise ValueError('Source bundle hash mismatch')
            seen=set()
            for g in evidence['games']:
                gid=str(g['game_id'])
                if not re.fullmatch(r'\d{10}',gid):raise ValueError('Invalid fixture ID')
                if gid in seen:raise ValueError('Duplicate evidence fixture')
                seen.add(gid)
                forecast=root/'frontend/data/nhl-forecasts'/('run-'+run)/(gid+'-ml.json')
                if not forecast.exists():
                    rejected.append(dict(run_id=run,game_id=gid,reason='missing_same_run_baseline'));continue
                envelope=json.loads(forecast.read_text());record=envelope['record']
                if freeze_prediction(record)['sha256']!=envelope.get('sha256') or envelope.get('frozen') is not True:raise ValueError('Forecast hash mismatch')
                if record.get('model_version')!=VERSION or record.get('market')!='ml':raise ValueError('Unexpected baseline version or market')
                if any(str(record[k])!=str(g[k]) for k in ('game_id','home','away','start_utc')):raise ValueError('Forecast fixture mismatch')
                if not parse_utc(evidence['as_of_utc'])==parse_utc(g['feature_as_of_utc'])<=parse_utc(record['prediction_as_of_utc'])<parse_utc(g['start_utc']):raise ValueError('Evidence after issuance or start')
                p=record['probabilities']['home']
                if not 0<p<1:raise ValueError('Baseline must be strictly probabilistic')
                values={};reason=None
                for side in ('home','away'):
                    team=g['teams'][g[side]];history=team.get('goalie_prior_statistics')
                    if team.get('goalie_provider_status')!='confirmed' or type(team.get('goalie_player_id')) is not int or team['goalie_player_id']<=0:
                        reason='missing_provider_confirmed_goalie_identity';break
                    if not history:reason='missing_prior_goalie_history';break
                    if parse_utc(history['source']['retrieved_at'])>parse_utc(g['feature_as_of_utc']):raise ValueError('Future goalie history')
                    if date.fromisoformat(history['cutoff_exclusive'])>parse_utc(g['feature_as_of_utc']).date():raise ValueError('Future historical cutoff')
                    metric=history['season_to_date'];sv=metric['save_pct']
                    if type(metric.get('games')) is not int or metric['games']<=0 or type(sv) not in (int,float) or not math.isfinite(sv) or not 0<=sv<=1 or type(metric['shots_against']) is not int or metric['shots_against']<=0:raise ValueError('Malformed prior rate')
                    if type(metric['saves']) is not int or not 0<=metric['saves']<=metric['shots_against'] or abs(sv-metric['saves']/metric['shots_against'])>1e-5:raise ValueError('Inconsistent save rate')
                    values[side]=dict(player_id=team['goalie_player_id'],save_pct=sv,shots=metric['shots_against'])
                if reason:
                    rejected.append(dict(run_id=run,game_id=gid,reason=reason));continue
                if values['home']['player_id']==values['away']['player_id']:raise ValueError('Same goalie on opposing teams')
                row=dict(game_id=gid,run_id=run,home=g['home'],away=g['away'],start_utc=g['start_utc'],date=parse_utc(g['start_utc']).astimezone(ZoneInfo('America/Santiago')).date().isoformat(),feature_as_of_utc=g['feature_as_of_utc'],prediction_as_of_utc=record['prediction_as_of_utc'],baseline_p_home=p,goalies=values,goalie_sv_difference=values['home']['save_pct']-values['away']['save_pct'],evidence_sha256=evidence['content_sha256'],forecast_sha256=envelope['sha256'])
                candidates[gid].append(row)
        except (KeyError,ValueError,TypeError,OSError,EOFError) as error:
            # Quarantine the whole run if any fixture fails integrity.
            for gid in list(candidates):candidates[gid]=[r for r in candidates[gid] if r['run_id']!=run]
            rejected.append(dict(run_id=run,reason='invalid_evidence',detail=str(error)[:160]))
    rows=[];pending=[];duplicate_issuances=0
    for gid,choices in sorted(candidates.items()):
        if not choices:continue
        row=min(choices,key=lambda r:(parse_utc(r['prediction_as_of_utc']),int(r['run_id'])))
        duplicate_issuances+=len(choices)-1
        if gid not in labels:
            pending.append(row);continue
        game,y,sha,available=labels[gid]
        if any(str(game[k])!=str(row[k]) for k in ('home','away','start_utc')):raise ValueError('Official result fixture mismatch')
        if parse_utc(available)<=parse_utc(row['start_utc']):raise ValueError('Premature outcome')
        rows.append(dict(row,y_home_win=int(y=='home'),outcome_report_sha256=sha,outcome_available_at_utc=available))
    rows.sort(key=lambda r:(r['date'],r['game_id']))
    return dict(kind='nhl_prospective_goalie_cohort_v1',exposure='provider_confirmed_goalie_not_independent_starter_confirmation',selection='earliest eligible same-run issuance per fixture',rows=rows,pending=pending,excluded=rejected,duplicate_issuances_discarded=duplicate_issuances,status='awaiting_date_frozen_evaluation' if rows else 'insufficient_final_results',probabilities_modified=False,automatic_promotion=False)


def evaluate(data,fit_through,validation_through,test_through):
    for day in (fit_through,validation_through,test_through):date.fromisoformat(day)
    if not fit_through<validation_through<test_through:raise ValueError('Ordered fixed evaluation dates required')
    if data.get('kind')!='nhl_prospective_goalie_cohort_v1':raise ValueError('Invalid cohort')
    rows=data['rows']
    if len({r['game_id'] for r in rows})!=len(rows):raise ValueError('Duplicate cohort fixture')
    for r in rows:
        date.fromisoformat(r['date'])
        if type(r['y_home_win']) is not int or r['y_home_win'] not in (0,1) or not 0<r['baseline_p_home']<1 or not math.isfinite(r['goalie_sv_difference']):raise ValueError('Invalid evaluation row')
    fit=[r for r in rows if r['date']<=fit_through];validation=[r for r in rows if fit_through<r['date']<=validation_through];test=[r for r in rows if validation_through<r['date']<=test_through]
    base=dict(kind='nhl_prospective_goalie_evaluation_v1',protocol='goalie-v1-fixed-dates',fit_through=fit_through,validation_through=validation_through,test_through=test_through,fit_n=len(fit),validation_n=len(validation),test_n=len(test),automatic_promotion=False,probabilities_modified=False)
    # Operational minimums, never certificates of predictive validity.
    if len(fit)<400 or len(validation)<50 or len(test)<100 or min(len({r['date'] for r in g}) for g in (fit,validation,test))<2 or len({r['y_home_win'] for r in fit})<2:
        return dict(base,status='insufficient_chronological_evidence',models=None)
    if max(parse_utc(r['outcome_available_at_utc']) for r in fit)>=min(parse_utc(r['prediction_as_of_utc']) for r in validation) or max(parse_utc(r['outcome_available_at_utc']) for r in validation)>=min(parse_utc(r['prediction_as_of_utc']) for r in test):
        return dict(base,status='outcomes_unavailable_at_training_cutoff',models=None)
    xs=lambda group,goalie:[[logit(r['baseline_p_home'])]+([r['goalie_sv_difference']] if goalie else []) for r in group]
    ys=lambda group:[r['y_home_win'] for r in group]
    results={'baseline':[r['baseline_p_home'] for r in test]};models={}
    for name,goalie in [('recalibration_only',False),('recalibration_plus_goalie',True)]:
        trials=[]
        for penalty in (.005,.02,.1):
            model=train(xs(fit,goalie),ys(fit),l2=penalty)
            loss=score([predict(model,x) for x in xs(validation,goalie)],ys(validation))['log_loss']
            trials.append((loss,penalty,model))
        _,penalty,model=min(trials,key=lambda t:(t[0],t[1]))
        models[name]=dict(penalty=penalty,model=model,validation_grid=[dict(log_loss=loss,penalty=p) for loss,p,_ in trials])
        results[name]=[predict(model,x) for x in xs(test,goalie)]
    rng=random.Random(291);days=sorted({r['date'] for r in test});blocks=[[i for i,r in enumerate(test) if r['date']==day] for day in days]
    intervals={}
    candidate=results['recalibration_plus_goalie'];y=ys(test)
    for reference in ('baseline','recalibration_only'):
        paired=[((p-t)**2-(q-t)**2,-t*math.log(max(p,1e-12))-(1-t)*math.log(max(1-p,1e-12))+t*math.log(max(q,1e-12))+(1-t)*math.log(max(1-q,1e-12))) for p,q,t in zip(candidate,results[reference],y)]
        samples=[]
        for _ in range(1000):
            ids=[i for _ in days for i in rng.choice(blocks)]
            samples.append([sum(paired[i][j] for i in ids)/len(ids) for j in (0,1)])
        intervals[reference]={name:dict(delta=sum(p[j] for p in paired)/len(paired),ci95=[quantile([s[j] for s in samples],q) for q in (.025,.975)]) for j,name in enumerate(('brier','log_loss'))}
    calibration={name:[dict(range=[lo/10,(lo+1)/10],n=len(index),mean_prediction=sum(probs[i] for i in index)/len(index) if index else None,observed_home_win=sum(y[i] for i in index)/len(index) if index else None) for lo in range(10) for index in [[i for i,p in enumerate(probs) if min(9,int(p*10))==lo]]] for name,probs in results.items()}
    return dict(base,status='research_evaluated_not_promoted',input_rows_sha256=digest(fit+validation+test),calibration=calibration,test_date_blocks=len(days),models=models,metrics={name:score(p,y) for name,p in results.items()},paired_candidate_minus_reference=intervals,test_predictions=[dict(game_id=r['game_id'],date=r['date'],y_home_win=r['y_home_win'],**{name:p[i] for name,p in results.items()}) for i,r in enumerate(test)],limitations=['Date-block bootstrap does not remove all team dependence.','Provider assertion is the exposure, not independently confirmed actual starter.','Repeated test inspection is not independent validation.','Date cutoffs supplied by the caller are not independently attested precommitments.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--output',required=True)
    p.add_argument('--fit-through');p.add_argument('--validation-through');p.add_argument('--test-through');a=p.parse_args()
    result=cohort(a.repo)
    cuts=(a.fit_through,a.validation_through,a.test_through)
    if any(cuts):
        if not all(cuts):p.error('All three frozen date cutoffs are required')
        result=dict(cohort=result,evaluation=evaluate(result,*cuts))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);
    with out.open('x' if any(cuts) else 'w') as handle:handle.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result.get('status',result.get('evaluation',{}).get('status')),final_rows=len(result.get('rows',result.get('cohort',{}).get('rows',[]))))))
