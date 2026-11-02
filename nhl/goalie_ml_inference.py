"""ML-only experimental inference. Never silently replace the published baseline."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from nhl.goalie_prospective_evaluation import cohort, digest
from nhl.pulso_goalie_model_269 import logit, predict
from nhl.pulso_pregame_v7 import parse_utc

CONTRACT='baseline-logit-plus-season-prior-sv-difference-v1'
FEATURES=['baseline_logit','home_sv_minus_away_sv']


def validate_parameters(model, dimensions):
    if not isinstance(model,dict):raise ValueError('Missing fitted parameters')
    for field,n in [('coef',dimensions+1),('mean',dimensions),('scale',dimensions)]:
        values=model.get(field)
        if not isinstance(values,list) or len(values)!=n or any(type(x) not in (int,float) or not math.isfinite(x) for x in values):raise ValueError('Invalid '+field+' dimensions or values')
    if any(x<=0 for x in model['scale']):raise ValueError('Invalid feature scale')


def package(evaluation, as_of):
    """Export only evaluated prospective models; historic #269 has another contract."""
    if evaluation.get('kind')!='nhl_prospective_goalie_evaluation_v1' or evaluation.get('status')!='research_evaluated_not_promoted' or evaluation.get('protocol')!='goalie-v1-fixed-dates':raise ValueError('No compatible evaluated candidate')
    if parse_utc(as_of).date().isoformat()<=evaluation['test_through']:raise ValueError('Evaluation interval not complete at export')
    if not evaluation['fit_through']<evaluation['validation_through']<evaluation['test_through']:raise ValueError('Invalid evaluation cutoffs')
    if evaluation['fit_n']<400 or evaluation['validation_n']<50 or evaluation['test_n']<100:raise ValueError('Insufficient evaluated coverage')
    for name in ('baseline','recalibration_only','recalibration_plus_goalie'):
        if evaluation['metrics'][name]['n']!=evaluation['test_n']:raise ValueError('Unaligned evaluation')
    models=evaluation['models']
    validate_parameters(models['recalibration_only']['model'],1)
    validate_parameters(models['recalibration_plus_goalie']['model'],2)
    result=dict(kind='nhl_goalie_ml_candidate_v1',contract=CONTRACT,features=FEATURES,
        available_at_utc=as_of,training_cutoff=evaluation['fit_through'],validation_cutoff=evaluation['validation_through'],evaluation_cutoff=evaluation['test_through'],
        candidate=models['recalibration_plus_goalie']['model'],recalibration=models['recalibration_only']['model'],
        evaluation_sha256=digest(evaluation),evaluation_input_sha256=evaluation['input_rows_sha256'],holdout_metrics=evaluation['metrics'],
        exposure='provider_confirmed_goalie_not_independent_starter_confirmation',status='experimental_not_promoted',automatic_promotion=False,production_approved=False)
    return dict(result,artifact_sha256=digest(result))


def validate_artifact(model, at):
    if model.get('kind')!='nhl_goalie_ml_candidate_v1' or model.get('contract')!=CONTRACT or model.get('features')!=FEATURES:raise ValueError('Incompatible feature contract')
    if digest({k:v for k,v in model.items() if k!='artifact_sha256'})!=model.get('artifact_sha256'):raise ValueError('Artifact integrity mismatch')
    if model.get('status')!='experimental_not_promoted' or model.get('production_approved') is not False:raise ValueError('Unapproved model authority')
    if model.get('exposure')!='provider_confirmed_goalie_not_independent_starter_confirmation':raise ValueError('Incompatible goalie exposure')
    if parse_utc(model['available_at_utc'])>at or model['evaluation_cutoff']>=at.date().isoformat():raise ValueError('Model unavailable at inference time')
    validate_parameters(model.get('candidate'),2);validate_parameters(model.get('recalibration'),1)



def infer_pairings(repository,run_id,game,scenarios,history,model,at):
    """Conditional 'if X plays against Y' ML, no guessed starter or scenario weights."""
    from nhl.pulso_collective_audit_208 import freeze_prediction
    if scenarios.get('kind')!='nhl_goalie_conditional_scenarios_258' or history.get('kind')!='nhl_all_goalie_candidates_history_260':raise ValueError('Wrong scenario input contract')
    if parse_utc(scenarios['as_of_utc'])!=parse_utc(history['as_of_utc']):raise ValueError('Scenario capture mismatch')
    gid=str(game['game_id'])
    matches=[r for r in scenarios['games'] if str(r['game_id'])==gid]
    histories=[r for r in history['games'] if str(r['game_id'])==gid]
    if len(matches)!=1 or len(histories)!=1:raise ValueError('Missing or duplicate scenario fixture')
    sc,observed=matches[0],histories[0]
    if any((r['home'],r['away'])!=(game['home'],game['away']) for r in (sc,observed)):raise ValueError('Scenario fixture mismatch')
    path=Path(repository)/'frontend/data/nhl-forecasts'/('run-'+str(run_id))/(gid+'-ml.json')
    envelope=json.loads(path.read_text());baseline=envelope['record']
    if envelope.get('sha256')!=freeze_prediction(baseline)['sha256']:raise ValueError('Scenario baseline integrity mismatch')
    if any(str(baseline[k])!=str(game[k]) for k in ('game_id','home','away','start_utc')) or abs(baseline['probabilities']['home']-game['ml']['home'])>1e-12:raise ValueError('Scenario baseline emission mismatch')
    issued=parse_utc(baseline['prediction_as_of_utc']);start=parse_utc(game['start_utc'])
    if not parse_utc(scenarios['as_of_utc'])<=issued<start:raise ValueError('Scenario inputs postdate forecast')
    candidates={}
    for team in (game['home'],game['away']):
        rows=observed['teams'].get(team,[]);index={r['player_id']:r for r in rows}
        if len(index)!=len(rows):raise ValueError('Duplicate goalie history identity')
        candidates[team]=index
    expected={(h['player_id'],a['player_id']) for h in sc['goalie_candidates'][game['home']] for a in sc['goalie_candidates'][game['away']]}
    actual={(r['home_goalie']['player_id'],r['away_goalie']['player_id']) for r in sc['scenarios']}
    if expected!=actual or len(actual)!=len(sc['scenarios']):raise ValueError('Incomplete or duplicate goalie combinations')
    result=[]
    for pair in sc['scenarios']:
        row=dict(home_goalie=pair['home_goalie'],away_goalie=pair['away_goalie'],candidate_p_home=None,candidate_p_away=None,recalibration_p_home=None,delta_vs_baseline_pp=None,delta_vs_recalibration_pp=None,status='goalie_model_not_executed',reasons=[])
        reasons=row['reasons'];rates=[]
        if pair['home_goalie']['player_id']==pair['away_goalie']['player_id']:reasons.append('same_goalie_on_both_teams')
        if model is None:reasons.append('missing_fitted_model')
        else:
            try:
                validate_artifact(model,at)
                if parse_utc(model['available_at_utc'])>issued:reasons.append('model_unavailable_at_baseline_issuance')
            except (ValueError,KeyError,TypeError):reasons.append('invalid_or_incompatible_model')
        if at>=start:reasons.append('fixture_already_started')
        for side in ('home','away'):
            goalie=pair[side+'_goalie'];record=candidates[game[side]].get(goalie['player_id'])
            if not record or record.get('name')!=goalie['name'] or record.get('status')!='observed':
                reasons.append('missing_prior_goalie_history');continue
            try:
                source=record['source'];m=record['metrics'];season=m['season_to_date']
                if not parse_utc(scenarios['as_of_utc'])<=parse_utc(source['retrieved_at'])<=issued:raise ValueError('History time mismatch')
                if m['cutoff_exclusive']!=parse_utc(scenarios['as_of_utc']).date().isoformat():raise ValueError('History cutoff mismatch')
                expected_url='https://api-web.nhle.com/v1/player/'+str(goalie['player_id'])+'/game-log/'
                if not source.get('url','').startswith(expected_url) or len(source.get('sha256',''))!=64:raise ValueError('Wrong history provenance')
                shots,saves=season['shots_against'],season['saves']
                if type(shots) is not int or type(saves) is not int or not 0<=saves<=shots or shots<=0 or not math.isfinite(season['save_pct']) or abs(season['save_pct']-saves/shots)>1e-5:raise ValueError('Invalid goalie counts')
                rates.append(saves/shots)
            except (ValueError,TypeError,KeyError):reasons.append('invalid_goalie_history')
        row['reasons']=list(dict.fromkeys(reasons))
        if not row['reasons']:
            p=game['ml']['home'];candidate=predict(model['candidate'],[logit(p),rates[0]-rates[1]])
            control=predict(model['recalibration'],[logit(p)])
            if not all(math.isfinite(v) and 0<=v<=1 for v in (candidate,control)):raise ValueError('Invalid conditional ML')
            row.update(candidate_p_home=candidate,candidate_p_away=1-candidate,recalibration_p_home=control,delta_vs_baseline_pp=100*(candidate-p),delta_vs_recalibration_pp=100*(candidate-control),status='experimental_goalie_ml_executed')
        result.append(row)
    return dict(pairings=result,scenario_count=len(result),unresolved_editorial_candidates=sc.get('unresolved_editorial_candidates',{}),
        scenario_history_sha256=digest(history),scenario_inputs_sha256=digest(scenarios),baseline_forecast_sha256=envelope['sha256'],baseline_as_of_utc=baseline['prediction_as_of_utc'],
        scenario_interpretation='conditional_if_each_named_pair_plays_not_a_weighted_or_confirmed_starter_forecast')


def infer(repository, run_id, slate, model=None, at=None, scenarios=None, scenario_history=None):
    """Use this run's evidence, never a later/earlier issuance of the same game."""
    at=at or datetime.now(timezone.utc)
    data=cohort(repository,run_id=run_id)
    rows={r['game_id']:r for r in data['rows']+data['pending']}
    rejection={r.get('game_id'):r['reason'] for r in data['excluded']}
    model_issue=None
    assessment=None
    try:
        if model is None:
            model_issue='missing_fitted_model'
            assessment_path=Path(repository)/'nhl/models/goalie-ml-assessment.json'
            if assessment_path.is_file():
                observed=json.loads(assessment_path.read_text())
                if observed.get('kind')=='nhl_goalie_ml_assessment_v1' and observed.get('decision')=='not_approved_no_incremental_gain':
                    metrics=observed['metrics']
                    if any(metrics['recalibration_plus_goalie'][m]>=metrics[ref][m] for ref in ('baseline','recalibration_only') for m in ('brier','log_loss')):
                        assessment=observed;model_issue='model_failed_incremental_evaluation'
        else:validate_artifact(model,at)
    except (ValueError,KeyError,TypeError) as error:model_issue='invalid_or_incompatible_model: '+str(error)
    if slate.get('kind')!='nhl_research_daily_presentation_275' or slate.get('official') is not False or slate.get('odds_used') is not False:raise ValueError('Unverified baseline presentation')
    if str(slate.get('run_id'))!=str(run_id):raise ValueError('Presentation belongs to another run')
    if len({str(g['game_id']) for g in slate['games']})!=len(slate['games']):raise ValueError('Duplicate slate fixture')
    output=[]
    for g in slate['games']:
        gid=str(g['game_id']);row=rows.get(gid)
        p=g.get('ml',{}).get('home') if g.get('ml') else None
        result=dict(game_id=gid,home=g['home'],away=g['away'],start_utc=g['start_utc'],baseline_p_home=p,
            candidate_p_home=None,candidate_p_away=None,recalibration_p_home=None,delta_vs_baseline_pp=None,delta_vs_recalibration_pp=None,
            status='goalie_model_not_executed',reasons=[],computed_at_utc=at.isoformat())
        reasons=result['reasons']
        if model_issue:reasons.append(model_issue)
        if row is None:reasons.append(rejection.get(gid,'missing_verified_same_run_inputs'))
        if parse_utc(g['start_utc'])<=at:reasons.append('fixture_already_started')
        if row:
            if any(str(row[k])!=str(g[k]) for k in ('home','away','start_utc')):raise ValueError('Candidate fixture mismatch')
            if type(p) not in (int,float) or abs(p-row['baseline_p_home'])>1e-12:raise ValueError('Baseline emission mismatch')
            if parse_utc(row['prediction_as_of_utc'])>at:reasons.append('forecast_from_future')
            if model and not model_issue and parse_utc(model['available_at_utc'])>parse_utc(row['prediction_as_of_utc']):reasons.append('model_unavailable_at_baseline_issuance')
            result.update(feature_as_of_utc=row['feature_as_of_utc'],baseline_as_of_utc=row['prediction_as_of_utc'],evidence_sha256=row['evidence_sha256'],baseline_forecast_sha256=row['forecast_sha256'],goalies=row['goalies'])
        if not reasons:
            features=[logit(p),row['goalie_sv_difference']]
            candidate=predict(model['candidate'],features)
            control=predict(model['recalibration'],[features[0]])
            if not all(math.isfinite(x) and 0<=x<=1 for x in (candidate,control)):raise ValueError('Nonfinite inferred probability')
            result.update(candidate_p_home=candidate,candidate_p_away=1-candidate,recalibration_p_home=control,
                delta_vs_baseline_pp=100*(candidate-p),delta_vs_recalibration_pp=100*(candidate-control),
                status='experimental_goalie_ml_executed',model_sha256=model['artifact_sha256'])
        if scenarios is not None and scenario_history is not None and g.get('ml'):
            try:
                scenario_result=infer_pairings(repository,run_id,g,scenarios,scenario_history,model,at)
                result.update(scenario_result)
                if model is not None and not model_issue:result['model_sha256']=model['artifact_sha256']
            except (ValueError,KeyError,TypeError,OSError) as error:
                result.update(pairings=[],scenario_count=0,scenario_error=str(error)[:160])
        if assessment and model is None:
            for item in [result]+result.get('pairings',[]):
                item['reasons']=['model_failed_incremental_evaluation' if reason=='missing_fitted_model' else reason for reason in item['reasons']]
        output.append(result)
    return dict(kind='nhl_goalie_ml_comparison_v1',run_id=str(run_id),date=slate['date'],as_of_utc=at.isoformat(),games=output,
        candidate_assessment=assessment,published_baseline_replaced=False,market='ml',official=False,automatic_promotion=False,
        limitations=['ML-only candidate: RT and +3 retain their original model.','Differences between fitted models are not causal goalie effects.','Provider confirmation is not independent starter verification.'],input_exclusions=data['excluded'])


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    export=sub.add_parser('export');export.add_argument('--evaluation',required=True);export.add_argument('--output',required=True)
    run=sub.add_parser('run');run.add_argument('--repo',default='.');run.add_argument('--run-id',required=True);run.add_argument('--slate',required=True);run.add_argument('--model');run.add_argument('--output',required=True);run.add_argument('--scenarios');run.add_argument('--scenario-history')
    a=p.parse_args();now=datetime.now(timezone.utc)
    if a.command=='export':
        raw=json.loads(Path(a.evaluation).read_text());result=package(raw.get('evaluation',raw),now.isoformat())
    else:
        model=json.loads(Path(a.model).read_text()) if a.model and Path(a.model).is_file() else None

        if bool(a.scenarios)!=bool(a.scenario_history):p.error('Both scenario and candidate history paths required')
        scenarios=json.loads(Path(a.scenarios).read_text()) if a.scenarios else None
        history=json.loads(Path(a.scenario_history).read_text()) if a.scenario_history else None
        result=infer(a.repo,a.run_id,json.loads(Path(a.slate).read_text()),model,now,scenarios,history)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as handle:json.dump(result,handle,indent=2)
    print(json.dumps(dict(kind=result['kind'],status=result.get('status'),executed=sum(g['status']=='experimental_goalie_ml_executed' for g in result.get('games',[])))))
