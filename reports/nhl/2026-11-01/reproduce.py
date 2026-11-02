"""Reproduce one dated postmortem from saved official responses and frozen forecasts.

No training, source forecast edits, betting calculations, or automatic promotion.
Usage: python reproduce.py --repo CHECKOUT --raw RAW_DIR --out OUTPUT_DIR
"""
import argparse,gzip,hashlib,json,math,sys
from datetime import datetime,timezone
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--raw',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 repo=Path(a.repo).resolve();raw=Path(a.raw);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(repo))
 from nhl.pulso_collective_audit_208 import freeze_prediction,brier,logloss
 from nhl.pulso_pregame_v7 import parse_utc
 from nhl.pulso_official_outcome_audit_219 import label_from_pbp
 from nhl.historical_postgame_labels import labels as sorted_labels
 from nhl.pulso_forecast_score_217 import evaluate
 from nhl.historical_target_walkforward import CATEGORIES
 from nhl.pulso_prospective_compare_242 import collect_challenger,final_scores,evaluate as compare
 observed=datetime.now(timezone.utc).isoformat();day='2026-11-01';score=json.loads((raw/'score.json').read_text());ids={str(g['id']) for g in score['games']}
 assert len(ids)==5 and all(g['gameState'] in ('OFF','FINAL') for g in score['games'])
 provenance=[];(out/'evidence').mkdir(exist_ok=True)
 for file in sorted(raw.glob('*.json')):
  data=file.read_bytes();destination=out/'evidence'/(file.name+'.gz');destination.write_bytes(gzip.compress(data,mtime=0))
  url='https://api-web.nhle.com/v1/score/'+day if file.name=='score.json' else 'https://api-web.nhle.com/v1/gamecenter/'+file.name.split('-')[0]+'/play-by-play'
  provenance.append({'file':'evidence/'+destination.name,'source_url':url,'uncompressed_sha256':sha(data),'gzip_sha256':sha(destination.read_bytes()),'retrieved_at_utc':datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat()})
 labels=[];details={}
 for final in score['games']:
  gid=str(final['id']);pbp=json.loads((raw/(gid+'-pbp.json')).read_text());label=label_from_pbp(pbp)
  assert label and pbp['homeTeam']['score']==final['homeTeam']['score'] and pbp['awayTeam']['score']==final['awayTeam']['score']
  game={'game_id':gid,'date':day,'home':pbp['homeTeam']['abbrev'],'away':pbp['awayTeam']['abbrev'],
   'result_final':{'home_goals':pbp['homeTeam']['score'],'away_goals':pbp['awayTeam']['score']},
   'boxscore':{'home_team':{'id':pbp['homeTeam']['id']},'away_team':{'id':pbp['awayTeam']['id']}},
   'goal_events':[{'event_id':e.get('eventId'),'period':e['periodDescriptor']['number'],'period_type':e['periodDescriptor']['periodType'],'time_in_period':e.get('timeInPeriod'),'owner_team_id':e.get('details',{}).get('eventOwnerTeamId'),'home_score':e.get('details',{}).get('homeScore'),'away_score':e.get('details',{}).get('awayScore')} for e in pbp['plays'] if e.get('typeDescKey')=='goal']}
  independent=sorted_labels(game)
  assert label['ml_winner']==independent['ml_winner'] and label['rt_result']==independent['rt_result'] and label['first_to_plus3']==(independent['first_to_plus3'] or 'None')
  assert (label['home_reached_plus3']=='True')==independent['home_reached_plus3'] and (label['away_reached_plus3']=='True')==independent['away_reached_plus3']
  labels.append(label);details[gid]={'game_id':gid,'home':label['home'],'away':label['away'],'home_score':pbp['homeTeam']['score'],'away_score':pbp['awayTeam']['score'],'start_utc':pbp['startTimeUTC'],'final_state':pbp['gameState'],'official_labels':independent,'market_scores':[]}
 earliest={};duplicates=0;paths={}
 for file in sorted((repo/'frontend/data/nhl-forecasts').glob('*/*.json')):
  envelope=json.loads(file.read_text());r=envelope.get('record',{});gid=str(r.get('game_id'))
  if gid not in ids:continue
  assert envelope.get('frozen') is True and freeze_prediction(r)['sha256']==envelope['sha256']
  assert parse_utc(r['prediction_as_of_utc'])<parse_utc(r['start_utc']) and r['start_utc']==details[gid]['start_utc']
  key=(gid,r['model_version'],r['market']);duplicates+=1
  if key not in earliest or parse_utc(r['prediction_as_of_utc'])<parse_utc(earliest[key]['record']['prediction_as_of_utc']):earliest[key]=envelope;paths[key]=str(file.relative_to(repo))
 assert len(earliest)==25
 selected=[];by_id={x['game_id']:x for x in labels};correct={m:0 for m in CATEGORIES};expected={m:[] for m in CATEGORIES}
 for key,envelope in sorted(earliest.items()):
  gid,model,market=key;r=envelope['record'];label=by_id[gid]
  outcome={'ml':label['ml_winner'],'rt':label['rt_result'],'first3':'none' if label['first_to_plus3']=='None' else label['first_to_plus3'],'home3':'yes' if label['home_reached_plus3']=='True' else 'no','away3':'yes' if label['away_reached_plus3']=='True' else 'no'}[market]
  probs=r['probabilities'];modal=max(probs,key=probs.get);correct[market]+=int(modal==outcome)
  row={'market':market,'model_version':model,'probabilities':probs,'actual':outcome,'modal_class':modal,'modal_correct':modal==outcome,'realized_probability':probs[outcome],
   'brier':brier([probs[c] for c in CATEGORIES[market]],outcome,CATEGORIES[market]),'log_loss':-math.log(max(1e-12,probs[outcome])),
   'prediction_as_of_utc':r['prediction_as_of_utc'],'source_path':paths[key],'forecast_sha256':envelope['sha256']}
  details[gid]['market_scores'].append(row);selected.append({'source_path':paths[key],'envelope':envelope})
  if market in ('home3','away3'):expected[market].append(probs['yes'])
  if market=='first3':expected[market].append(1-probs['none'])
 audit=evaluate(list(earliest.values()),labels);assert audit['scored']==25 and not audit['pending']
 baseline={gid:{'model':e['record']['model_version'],'home':e['record']['home'],'away':e['record']['away'],'start_utc':e['record']['start_utc'],'as_of':e['record']['prediction_as_of_utc'],'p_home':e['record']['probabilities']['home']} for (gid,model,market),e in earliest.items() if market=='ml'}
 challenger={gid:x for gid,x in collect_challenger((repo/'frontend/data/nhl-shadow').glob('run-*/shadow.json')).items() if gid in ids}
 paired=compare(baseline,challenger,final_scores(score))
 report={'kind':'nhl_dated_postmortem','date':day,'generated_at_utc':observed,'repo_revision':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
  'selection_policy':'earliest valid pregame forecast per game/model/market; never count reruns as independent observations',
  'source_forecast_files':duplicates,'unique_games':5,'unique_market_forecasts':25,'discarded_repeated_issuances':duplicates-25,'source_validation':'official score API + PBP, checked with two existing outcome reconstructors',
  'brier_definition':'mean squared class error averaged across classes; binary equals conventional (p-y)^2; do not compare absolute values across different market dimensions',
  'metrics':[{**m,'modal_correct':correct[m['market']],'modal_total':5} for m in audit['metrics']],
  'observed_plus3':{'home_yes':sum(l['home_reached_plus3']=='True' for l in labels),'away_yes':sum(l['away_reached_plus3']=='True' for l in labels),'any_team_yes':sum(l['first_to_plus3']!='None' for l in labels),'expected_home_yes':sum(expected['home3']),'expected_away_yes':sum(expected['away3']),'expected_any_team_yes':sum(expected['first3'])},
  'games':[details[k] for k in sorted(details)],'paired_ml_comparison':paired,'sources':provenance,'official_model_promoted':False,'parameters_changed':False,
  'limitations':['Five games only; 25 market forecasts are correlated, not 25 independent games.','Frozen hashes verify integrity, not an independent attestation of original collection time.','No ROI, profit or value claim; no bookmaker odds were used.','Outcome-only model is not the full lineup/goalie sporting model.']}
 (out/'postmortem.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');(out/'selected-frozen-forecasts.json').write_text(json.dumps(selected,indent=2)+'\n')
 learning={'kind':'nhl_postgame_learning_observations','date':day,'available_at_utc':observed,'data_class':'POSTGAME_LABELS_NOT_PREGAME_FEATURES','games':[details[k]['official_labels'] for k in sorted(details)],'training_status':'quarantined_for_future_chronological_training','applied_to_live_parameters':False,'promotion_authorized':False,'source_manifest':'postmortem.json#sources',
  'hypotheses':[{'id':'NHL-20261101-L1','observation':'ANA-OTT: both sides reached +3, Ottawa first, Anaheim won.','action':'Retain separate path-dependent targets and permanent regression case; never derive reached+3 from final margin.'},
   {'id':'NHL-20261101-L2','observation':'All five games reached a +3 lead, while none was the modal first3 class in all five forecasts.','action':'Monitor rare-event calibration on a larger untouched cohort; do not refit from this day.'},
   {'id':'NHL-20261101-L3','observation':'Repeated runs produced duplicate game/market predictions.','action':'Score one predeclared issuance per fixture/model/market; evaluate late-update policies separately.'}],
  'next_validation':'Fit only on past development data; validate calibration on separate dates; compare frozen challenger on untouched holdout before any promotion.'}
 (out/'learning-observations.json').write_text(json.dumps(learning,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'games':report['unique_games'],'scored':audit['scored'],'metrics':report['metrics'],'plus3':report['observed_plus3'],'paired':paired['paired_completed']},indent=2))
if __name__=='__main__':main()
