"""Dated, repeatable NHL final-outcome audit. Never trains or promotes models."""
import argparse,gzip,hashlib,json,math,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from nhl.historical_target_walkforward import CATEGORIES
from nhl.historical_postgame_labels import labels as reconstruct_sorted
from nhl.pulso_official_outcome_audit_219 import label_from_pbp
from nhl.pulso_collective_audit_208 import freeze_prediction,brier
from nhl.pulso_pregame_v7 import parse_utc
from nhl.pulso_prospective_compare_242 import collect_challenger,final_scores,evaluate as paired_evaluate

TZ=ZoneInfo('America/Santiago')
BASE='https://api-web.nhle.com/v1/'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def fetch_json(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PULSO-NHL-Postmortem/1.0'}),timeout=25) as response:return json.load(response)
def local_day(value):return parse_utc(value).astimezone(TZ).date().isoformat()
def original_forecasts(repo,day):
 selected={};paths={};count=0
 for path in sorted((Path(repo)/'frontend/data/nhl-forecasts').glob('run-*/*.json')):
  envelope=read(path);row=envelope.get('record',{})
  if local_day(row['start_utc'])!=day:continue
  if envelope.get('frozen') is not True or freeze_prediction(row)['sha256']!=envelope.get('sha256'):raise ValueError('Invalid frozen forecast: '+str(path))
  if row.get('official') is not False or row.get('odds_used_in_model') is not False:raise ValueError('Not an experimental odds-free forecast')
  count+=1;key=(str(row['game_id']),row['model_version'],row['market'])
  if key not in selected or parse_utc(row['prediction_as_of_utc'])<parse_utc(selected[key]['record']['prediction_as_of_utc']):selected[key]=envelope;paths[key]=str(path.relative_to(repo))
 return selected,paths,count

def checked_label(payload,score):
 if payload.get('gameState') not in ('OFF','FINAL'):return None
 if str(payload.get('id'))!=str(score['id']):raise ValueError('Result ID mismatch')
 for side in ('homeTeam','awayTeam'):
  if any(payload[side].get(k)!=score[side].get(k) for k in ('abbrev','score')):raise ValueError('Scoreboard and PBP disagree')
 label=label_from_pbp(payload)
 game={'game_id':str(payload['id']),'date':local_day(payload['startTimeUTC']),'home':payload['homeTeam']['abbrev'],'away':payload['awayTeam']['abbrev'],
  'result_final':{'home_goals':payload['homeTeam']['score'],'away_goals':payload['awayTeam']['score']},
  'boxscore':{'home_team':{'id':payload['homeTeam']['id']},'away_team':{'id':payload['awayTeam']['id']}},
  'goal_events':[{'event_id':e.get('eventId'),'period':e['periodDescriptor']['number'],'period_type':e['periodDescriptor']['periodType'],'time_in_period':e.get('timeInPeriod'),'owner_team_id':e.get('details',{}).get('eventOwnerTeamId'),'home_score':e.get('details',{}).get('homeScore'),'away_score':e.get('details',{}).get('awayScore')} for e in payload.get('plays',[]) if e.get('typeDescKey')=='goal']}
 other=reconstruct_sorted(game)
 for k in ('ml_winner','rt_result'):
  if label[k]!=other[k]:raise ValueError('Outcome reconstructors disagree')
 if label['first_to_plus3']!=(other['first_to_plus3'] or 'None'):raise ValueError('First +3 reconstructors disagree')
 for k in ('home_reached_plus3','away_reached_plus3'):
  if (label[k]=='True')!=other[k]:raise ValueError('+3 reconstructors disagree')
 return other

def analyze(repo,day,get=fetch_json,now=None):
 now=now or datetime.now(timezone.utc);datetime.strptime(day,'%Y-%m-%d')
 if day>now.astimezone(TZ).date().isoformat():raise ValueError('Cannot postmortem a future date')
 chosen,paths,total=original_forecasts(repo,day);sources={};errors={};score_games={}
 def capture(url):
  payload=get(url);sources[url]=payload;return payload
 # Adjacent official schedule days cover calendar boundaries in Chile.
 for delta in (-1,0,1):
  date=(datetime.strptime(day,'%Y-%m-%d')+timedelta(days=delta)).date().isoformat();url=BASE+'score/'+date
  try:
   data=capture(url)
   if not isinstance(data.get('games'),list):raise ValueError('Missing official games array')
   for game in data['games']:
    if local_day(game['startTimeUTC'])!=day:continue
    gid=str(game['id'])
    if gid in score_games and score_games[gid]!=game:raise ValueError('Conflicting official scoreboard')
    score_games[gid]=game
  except Exception as exc:errors[url]=type(exc).__name__+': '+str(exc)[:160]
 expected={str(k[0]) for k in chosen};missing=sorted(expected-set(score_games))
 if missing:errors['missing_forecast_games']='Forecasts absent from official calendar: '+','.join(missing)
 labels={};pending=[]
 for gid,game in sorted(score_games.items()):
  if game.get('gameState') not in ('OFF','FINAL'):
   pending.append(gid);continue
  if gid not in expected:continue
  url=BASE+'gamecenter/'+gid+'/play-by-play'
  try:
   if parse_utc(game['startTimeUTC'])>=now:raise ValueError('Final reported before game start')
   value=checked_label(capture(url),game)
   if value is None:pending.append(gid)
   else:labels[gid]=value
  except Exception as exc:errors[url]=type(exc).__name__+': '+str(exc)[:160]
 rows=[];grouped=defaultdict(list)
 for key,envelope in sorted(chosen.items()):
  gid,model,market=key;r=envelope['record'];label=labels.get(gid)
  if not label:continue
  if any(r[k]!=label[k] for k in ('home','away')) or r['start_utc']!=score_games[gid]['startTimeUTC']:raise ValueError('Forecast/result identity mismatch')
  target={'ml':label['ml_winner'],'rt':label['rt_result'],'first3':label['first_to_plus3'] or 'none','home3':'yes' if label['home_reached_plus3'] else 'no','away3':'yes' if label['away_reached_plus3'] else 'no'}[market]
  probabilities=r['probabilities'];modal=max(probabilities,key=probabilities.get)
  row={'game_id':gid,'model_version':model,'market':market,'probabilities':probabilities,'actual':target,'modal_class':modal,'modal_correct':modal==target,
   'brier':brier([probabilities[c] for c in CATEGORIES[market]],target,CATEGORIES[market]),'log_loss':-math.log(max(1e-12,probabilities[target])),
   'prediction_as_of_utc':r['prediction_as_of_utc'],'source_path':paths[key],'forecast_sha256':envelope['sha256']}
  rows.append(row);grouped[(model,market)].append(row)
 metrics=[{'model_version':model,'market':market,'n':len(v),'modal_correct':sum(r['modal_correct'] for r in v),'brier':round(sum(r['brier'] for r in v)/len(v),6),'log_loss':round(sum(r['log_loss'] for r in v)/len(v),6)} for (model,market),v in sorted(grouped.items())]
 games=[{'game_id':gid,'home':g['homeTeam']['abbrev'],'away':g['awayTeam']['abbrev'],'start_utc':g['startTimeUTC'],'state':g['gameState'],
  'home_score':g['homeTeam'].get('score') if g['gameState'] in ('OFF','FINAL') else None,'away_score':g['awayTeam'].get('score') if g['gameState'] in ('OFF','FINAL') else None,
  'prediction_available':gid in expected,'outcomes':labels.get(gid)} for gid,g in sorted(score_games.items())]
 baseline={gid:{'model':r['record']['model_version'],'home':r['record']['home'],'away':r['record']['away'],'start_utc':r['record']['start_utc'],'as_of':r['record']['prediction_as_of_utc'],'p_home':r['record']['probabilities']['home']} for (gid,model,market),r in chosen.items() if market=='ml'}
 paired=None
 if len({k[1] for k in chosen if k[2]=='ml'})==1:
  challenger={gid:r for gid,r in collect_challenger((Path(repo)/'frontend/data/nhl-shadow').glob('run-*/shadow.json')).items() if gid in expected}
  paired=paired_evaluate(baseline,challenger,final_scores({'games':[g for gid,g in score_games.items() if gid in labels]}))
 status='needs_review' if errors else 'pending_results' if pending else 'complete' if chosen else 'no_forecasts'
 core={'kind':'nhl_daily_postmortem','date':day,'timezone':'America/Santiago','pipeline_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'status':status,'complete':not errors and not pending,
  'official_games':len(games),'forecast_games':len(expected),'graded_games':len(labels),'market_forecasts_scored':len(rows),'unpredicted_games':sorted(set(score_games)-expected),
  'source_forecast_files':total,'unique_forecast_issuances':len(chosen),'selection_policy':'earliest valid pregame issuance per game/model/market',
  'pending_game_ids':pending,'source_errors':errors,'games':games,'market_scores':rows,'metrics':metrics,'paired_ml_comparison':paired,
  'source_hashes':{url:digest(payload) for url,payload in sorted(sources.items())},'automatic_promotion':False,'parameters_changed':False,
  'learning_state':'observations_only_pending_independent_validation','limitations':['Markets from the same game are correlated.','No parameter changes or promotion from daily results.','Hashes verify content, not independent original capture time.']}
 return core,sources,[{'source_path':paths[k],'envelope':v} for k,v in sorted(chosen.items())]

def save(repo,core,sources,forecasts,now=None):
 repo=Path(repo);now=now or datetime.now(timezone.utc);day=core['date'];public=repo/'frontend/data/nhl-postmortems'/(day+'.json');revision=digest(core)
 previous=read(public) if public.exists() else None
 # Never erase previously scored finals when an upstream temporarily regresses.
 if previous and (not set(g['game_id'] for g in previous['games'] if g.get('outcomes')).issubset(set(g['game_id'] for g in core['games'] if g.get('outcomes'))) or (previous['complete'] and not core['complete'])):
  return {'date':day,'status':'preserved_previous_result','upstream_status':core['status'],'source_errors':core['source_errors']}
 archive=repo/'reports/nhl/daily'/day/'revisions'/revision
 if archive.exists():
  stored=read(archive/'report.json')
  if digest({k:v for k,v in stored.items() if k not in ('revision_sha256','generated_at_utc','archive_path')})!=revision:raise ValueError('Immutable report revision changed')
  report=stored
 else:
  report={**core,'revision_sha256':revision,'generated_at_utc':now.isoformat(),'archive_path':str(archive.relative_to(repo))}
  write(archive/'report.json',report);write(archive/'selected-forecasts.json',forecasts)
  for url,payload in sources.items():
   name=digest(url)+'.json.gz';data=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();path=archive/'evidence'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(data,mtime=0))
  observations=[g['outcomes'] for g in core['games'] if g.get('outcomes')]
  learning={'kind':'nhl_postgame_learning','date':day,'available_at_utc':now.isoformat(),'report_revision':revision,'data_class':'POSTGAME_LABELS_NOT_PREGAME_FEATURES','observations':observations,
   'signals':[{'type':'both_sides_reached_plus3','game_id':g['game_id']} for g in observations if g['home_reached_plus3'] and g['away_reached_plus3']],
   'state':'quarantined_for_future_chronological_training','applied_to_live_parameters':False,'automatic_promotion':False,'next_step':'Validate hypotheses on untouched future data; daily outcomes alone never authorize parameter updates.'}
  write(archive/'learning.json',learning)
 write(public,report);write(repo/'nhl/learning/postmortems'/(day+'.json'),read(archive/'learning.json'))
 return {'date':day,'status':report['status'],'revision':revision,'graded_games':report['graded_games'],'source_errors':report['source_errors']}

def update_index(repo):
 repo=Path(repo);reports=[read(p) for p in sorted((repo/'frontend/data/nhl-postmortems').glob('*.json'))]
 summary={'kind':'nhl_postmortem_index','automatic_parameter_updates':False,'days':[{k:r[k] for k in ('date','status','complete','official_games','forecast_games','graded_games','market_forecasts_scored','metrics','revision_sha256','generated_at_utc')} for r in reports]}
 write(repo/'frontend/data/nhl-postmortem-latest.json',summary)
 return summary

def run(repo,days,get=fetch_json,now=None):
 outputs=[]
 for day in sorted(set(days)):
  core,sources,forecasts=analyze(Path(repo),day,get,now);outputs.append(save(repo,core,sources,forecasts,now))
 update_index(repo);return outputs

def main():
 p=argparse.ArgumentParser();p.add_argument('--date');p.add_argument('--lookback',type=int,default=7);p.add_argument('--repo',default='.')
 args=p.parse_args();today=datetime.now(TZ).date()
 if not 1<=args.lookback<=30:raise ValueError('Lookback must be 1 through 30')
 days=[args.date] if args.date else [(today-timedelta(days=i)).isoformat() for i in range(1,args.lookback+1)]
 result=run(Path(args.repo).resolve(),days);print(json.dumps(result,indent=2))
 for item in result:
  if item.get('source_errors'):print('::warning::NHL '+item['date']+' has source errors; missing results were not scored')
if __name__=='__main__':main()
