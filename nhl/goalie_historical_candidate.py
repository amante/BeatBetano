"""Fit a clearly labelled retrospective conditional-goalie research candidate.

Season-reset SV rates include every prior appearance, never the target game's stats.
Actual historical starter IDs are postgame observations, not pregame attestations.
"""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import csv
import hashlib
import json
from pathlib import Path
import zipfile
from nhl.historical_target_walkforward import CATEGORIES,prediction
from nhl.pulso_outcome_forecast_218 import PARAMS
from nhl.pulso_historical_features_267 import goalie_totals
from nhl.pulso_goalie_model_269 import train,predict,score,logit
from nhl.goalie_ml_inference import CONTRACT,FEATURES,validate_parameters
from nhl.goalie_prospective_evaluation import digest


def rebuild(labels,records,min_shots=50,warmup=200):
    by_id={str(r['game_id']):r for r in records}
    if len(by_id)!=len(records) or len({str(r['game_id']) for r in labels})!=len(labels):raise ValueError('Duplicate historical fixture')
    if set(by_id)!={str(r['game_id']) for r in labels}:raise ValueError('Incomplete historical cache')
    days=defaultdict(list)
    for label in labels:
        if str(label['game_id'])[4:6]!='02':raise ValueError('Regular-season games only')
        if label['ml_winner'] not in ('home','away'):raise ValueError('Invalid historical ML target')
        record=by_id[str(label['game_id'])]
        if any(record[k]!=label[k] for k in ('date','home','away')):raise ValueError('Historical identity mismatch')
        days[label['date']].append(label)
    goalie=defaultdict(lambda:[0,0,0]);bad=set();globals_={k:defaultdict(int) for k in CATEGORIES};teams=defaultdict(lambda:{k:defaultdict(int) for k in CATEGORIES})
    rows=[];excluded=[];past=0
    for day in sorted(days):
        for label in days[day]:
            gid=str(label['game_id']);season=gid[:4];record=by_id[gid];prior={}
            if record.get('verified_starters'):
                for side in ('home','away'):
                    source=record['teams'][side];pid=source.get('starter_id')
                    matches=[p for p in source['goalies'] if p['player_id']==pid and p.get('explicit_starter') is True]
                    if len(matches)!=1:continue
                    saves,shots,n=goalie[(season,pid)]
                    if shots>=max(1,min_shots) and (season,pid) not in bad:
                        prior[side]=dict(player_id=pid,saves=saves,shots=shots,games=n,save_pct=saves/shots)
            if len(prior)==2 and past>=warmup:
                shrink,weight=PARAMS['ml'];p=prediction(globals_,teams,label['home'],label['away'],'ml',shrink,weight)[0]
                rows.append(dict(game_id=gid,date=day,home=label['home'],away=label['away'],baseline_p_home=p,goalie_sv_difference=prior['home']['save_pct']-prior['away']['save_pct'],goalies=prior,y_home_win=int(label['ml_winner']=='home'),starter_identity_timing='postgame_observed'))
            else:excluded.append(dict(game_id=gid,reason='insufficient_prior_goalie_history_or_baseline_warmup'))
        # Every same-day row is frozen before any outcome/appearance is added.
        for label in days[day]:
            gid=str(label['game_id']);season=gid[:4];record=by_id[gid]
            for side in ('home','away'):
                for player in record['teams'][side]['goalies']:
                    key=(season,player['player_id']);totals=goalie_totals(player)
                    if totals is None:bad.add(key);continue
                    saves,shots=totals
                    if shots>0:
                        goalie[key][0]+=saves;goalie[key][1]+=shots;goalie[key][2]+=1
            y=label['ml_winner'];globals_['ml'][y]+=1;teams['home:'+label['home']]['ml'][y]+=1;teams['away:'+label['away']]['ml'][y]+=1;past+=1
    return rows,excluded


def evaluate(rows,fit_through='2025-11-28',validation_through='2026-03-02',test_through='2026-10-26'):
    if not fit_through<validation_through<test_through:raise ValueError('Invalid fixed cuts')
    fit=[r for r in rows if r['date']<=fit_through];val=[r for r in rows if fit_through<r['date']<=validation_through];test=[r for r in rows if validation_through<r['date']<=test_through]
    if len(fit)<400 or len(val)<50 or len(test)<100:raise ValueError('Insufficient chronological coverage')
    y=lambda group:[r['y_home_win'] for r in group]
    x=lambda group,extra:[[logit(r['baseline_p_home'])]+([r['goalie_sv_difference']] if extra else []) for r in group]
    arms={'baseline':[r['baseline_p_home'] for r in test]};models={}
    for name,extra in [('recalibration_only',False),('recalibration_plus_goalie',True)]:
        trials=[]
        for penalty in (.005,.02,.1):
            model=train(x(fit,extra),y(fit),l2=penalty)
            loss=score([predict(model,v) for v in x(val,extra)],y(val))['log_loss']
            trials.append((loss,penalty,model))
        _,penalty,model=min(trials,key=lambda item:(item[0],item[1]))
        models[name]=dict(model=model,penalty=penalty,validation_grid=[dict(penalty=p,log_loss=l) for l,p,_ in trials])
        arms[name]=[predict(model,v) for v in x(test,extra)]
    metrics={name:score(p,y(test)) for name,p in arms.items()}
    gain=all(metrics['recalibration_plus_goalie'][m]<metrics[ref][m] for ref in ('baseline','recalibration_only') for m in ('brier','log_loss'))
    return dict(decision='research_candidate_only_pending_prospective' if gain else 'not_approved_no_incremental_gain',kind='nhl_historical_goalie_candidate_evaluation_v1',status='retrospective_research_only',fit_through=fit_through,validation_through=validation_through,test_through=test_through,fit_n=len(fit),validation_n=len(val),test_n=len(test),models=models,metrics=metrics,input_rows_sha256=digest(rows),test_predictions=[dict(game_id=r['game_id'],date=r['date'],y_home_win=r['y_home_win'],**{name:p[i] for name,p in arms.items()}) for i,r in enumerate(test)],automatic_promotion=False,prospectively_validated=False,limitations=['Historical starter identity was observed postgame; conditional research, not a pregame lineup backtest.','These historical holdouts have been inspected in earlier research; this is not independent new evidence.','Baseline recalibration and goalie contribution must be distinguished.'])


def artifact(report,provenance,at):
    validate_parameters(report['models']['recalibration_plus_goalie']['model'],2);validate_parameters(report['models']['recalibration_only']['model'],1)
    if at[:10]<=report['test_through']:raise ValueError('Export must follow evaluation interval')
    result=dict(kind='nhl_goalie_ml_candidate_v1',contract=CONTRACT,features=FEATURES,available_at_utc=at,training_cutoff=report['fit_through'],validation_cutoff=report['validation_through'],evaluation_cutoff=report['test_through'],candidate=report['models']['recalibration_plus_goalie']['model'],recalibration=report['models']['recalibration_only']['model'],evaluation_sha256=digest(report),evaluation_input_sha256=report['input_rows_sha256'],holdout_metrics=report['metrics'],exposure='observed_historical_starter_conditional_hypothesis',feature_cutoff_rule='strictly_before_nhl_game_date',minimum_prior_shots=50,minimum_prior_games=1,decision=report['decision'],status='experimental_not_promoted',automatic_promotion=False,production_approved=False,prospectively_validated=False,provenance=provenance,limitations=report['limitations'])
    return dict(result,artifact_sha256=digest(result))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('labels','manifest','cache-zip','report-output','model-output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();raw=Path(a.labels).read_bytes();manifest=json.loads(Path(a.manifest).read_text())
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256'] or manifest['games']!=2811:raise ValueError('Label source integrity failed')
    labels=list(csv.DictReader(raw.decode().splitlines()));z=zipfile.ZipFile(a.cache_zip)
    if len(labels)!=2811:raise ValueError('Unexpected source count')
    records=[json.loads(z.read('historical-boxscores-268/'+str(r['game_id'])+'.json')) for r in labels]
    rows,excluded=rebuild(labels,records);report=evaluate(rows);report['excluded']=excluded
    provenance=dict(source_run_id='41260212394',source_artifact_id=13065631013,labels_sha256=manifest['sha256'],cache_zip_sha256=hashlib.sha256(Path(a.cache_zip).read_bytes()).hexdigest(),training_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    expected='c7382f94919b7c7a9f5d255dcef5ba91a978cc0d7bb4c31962e6bac21992b5cc'
    if provenance['cache_zip_sha256']!=expected:raise ValueError('Historical cache identity changed')
    report['provenance']=provenance
    model=artifact(report,provenance,datetime.now(timezone.utc).isoformat())
    for name,value in ((a.report_output,dict(report,provenance=provenance)),(a.model_output,model)):
        path=Path(name);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as out:json.dump(value,out,indent=2)
    print(json.dumps(dict(fit=report['fit_n'],validation=report['validation_n'],test=report['test_n'],metrics=report['metrics'])))
