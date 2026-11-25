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
 legacy=[]
 for path in sorted((Path(repo)/'frontend/data/nhl-forecasts').glob('run-*/*.json')):
  envelope=read(path);row=envelope.get('record',{})
  if local_day(row['start_utc'])!=day:continue
  if envelope.get('frozen') is not True or freeze_prediction(row)['sha256']!=envelope.get('sha256'):raise ValueError('Invalid frozen forecast: '+str(path))
  if row.get('official') is not False or row.get('odds_used_in_model') is not False:raise ValueError('Not an experimental odds-free forecast')
  legacy.append((envelope,str(path.relative_to(repo))))
 archive_root=Path(repo)/'frontend/data/forecast_archive/nhl'
 archived=[]
 for path in sorted(archive_root.rglob('*.json')) if archive_root.exists() else []:
  snapshot=read(path)
  if snapshot.get('sport')!='nhl' or snapshot.get('emission_kind')!='pregame':continue
  events=snapshot.get('events')
  if not isinstance(events,list):continue
  matching=[event for event in events if event.get('start_utc') and local_day(event['start_utc'])==day]
  if not matching:continue
  content_sha=snapshot.get('content_sha256')
  content={k:v for k,v in snapshot.items() if k!='content_sha256'}
  if not content_sha or digest(content)!=content_sha:raise ValueError('Invalid NHL forecast archive content hash: '+str(path))
  if snapshot.get('source_input_declares_no_odds') is not True or snapshot.get('odds_used_in_sport_model') is not False:
   continue
  model_output=snapshot.get('source_model_output')
  if not isinstance(model_output,dict):continue
  output_sha=snapshot.get('source_output_sha256')
  output_core={k:v for k,v in model_output.items() if k!='source_output_sha256'}
  if snapshot.get('source_output_sha256_scope')=='event' and (not output_sha or digest(output_core)!=output_sha):
   raise ValueError('Invalid NHL archived model-output hash: '+str(path))
  provenance=snapshot.get('model_provenance') or {}
  source_asof=provenance.get('predictor_input_as_of_utc') or snapshot.get('as_of_utc')
  issued=snapshot.get('emitted_at_utc') or snapshot.get('as_of_utc')
  if not source_asof or not issued or parse_utc(source_asof)>parse_utc(issued):
   raise ValueError('Invalid NHL archive forecast timing: '+str(path))
  for event in matching:
   forecast=event.get('forecast')
   if not isinstance(forecast,dict) or not isinstance(forecast.get('probabilities'),dict):continue
   event_id=str(event.get('event_id') or '')
   if str(model_output.get('event_id') or '')!=event_id:continue
   start=event['start_utc']
   if model_output.get('start_utc') and parse_utc(model_output['start_utc'])!=parse_utc(start):
    raise ValueError('NHL archive forecast start mismatch: '+event_id)
   home=model_output.get('home_team');away=model_output.get('away_team')
   participants=event.get('participants')
   if not home or not away or (participants and [str(home),str(away)]!=[str(x) for x in participants]):
    raise ValueError('NHL archive forecast teams mismatch: '+event_id)
   probabilities=forecast['probabilities']
   if set(probabilities)!={'home','away'} or any(type(probabilities[k]) not in (int,float) or not math.isfinite(probabilities[k]) or probabilities[k]<0 or probabilities[k]>1 for k in ('home','away')) or abs(sum(probabilities.values())-1)>1e-6:
    raise ValueError('Invalid NHL archived ML probabilities: '+event_id)
   if parse_utc(issued)>=parse_utc(start):raise ValueError('Postgame NHL archived forecast: '+event_id)
   team_stats=model_output.get('official_team_stats') or {}
   source_url=next((team_stats.get(side,{}).get('source_url') for side in ('home','away') if team_stats.get(side,{}).get('source_url')), 'https://api-web.nhle.com/v1/')
   model=forecast.get('model_version') or snapshot.get('source_revision') or 'unknown'
   verified=snapshot.get('verified_point_in_time_source') is True
   record={'game_id':event_id,'home':str(home),'away':str(away),'start_utc':start,
    'prediction_as_of_utc':issued,'source_asof_utc':source_asof,'source_url':source_url,
    'model_version':model,'market':'ml','probabilities':probabilities,
    'odds_used_in_model':False,'official':False,'point_in_time_sources_verified':verified,
    'forecast_source_classification':forecast.get('source_classification') or 'archived_model_output',
    'source_archive_content_sha256':content_sha,'source_output_sha256':output_sha}
   envelope={'record':record,'sha256':digest({'archive_content_sha256':content_sha,'source_output_sha256':output_sha,'event_id':event_id}),
    'frozen':True,'source_kind':'forecast_archive','archive_content_sha256':content_sha,
    'source_output_sha256':output_sha,'point_in_time_sources_verified':verified}
   archived.append((envelope,str(path.relative_to(repo))))
 for envelope,path in legacy+archived:
  row=envelope['record']
  if row.get('official') is not False or row.get('odds_used_in_model') is not False:raise ValueError('Not an experimental odds-free forecast')
  key=(str(row['game_id']),row['model_version'],row['market'])
  if key not in selected or parse_utc(row['prediction_as_of_utc'])<parse_utc(selected[key]['record']['prediction_as_of_utc']):
   selected[key]=envelope;paths[key]=path
 count=len(legacy)+len(archived)
 return selected,paths,count


def official_player_boxscore(payload, game_id, scoreboard):
 if str(payload.get('id'))!=str(game_id):raise ValueError('Player boxscore game ID mismatch')
 if scoreboard.get('gameDate') and payload.get('gameDate')!=scoreboard.get('gameDate'):raise ValueError('Player boxscore date mismatch')
 for side in ('home','away'):
  expected=scoreboard.get(side+'Team',{}).get('abbrev')
  observed=payload.get(side+'Team',{}).get('abbrev')
  if expected and observed and expected!=observed:raise ValueError('Player boxscore team mismatch')
 by_game=payload.get('playerByGameStats')
 if not isinstance(by_game,dict):raise ValueError('Official player statistics missing')
 teams={};starters={}
 for side in ('home','away'):
  entry=by_game.get(side+'Team')
  if not isinstance(entry,dict):raise ValueError('Official player team missing')
  players={}
  for section in ('forwards','defense'):
   rows=entry.get(section)
   if not isinstance(rows,list):raise ValueError('Official skater rows missing')
   for raw in rows:
    pid=raw.get('playerId')
    if type(pid) is not int or pid<=0:raise ValueError('Invalid official skater ID')
    if str(pid) in players:raise ValueError('Duplicate official skater ID')
    values={}
    for key in ('goals','assists','points'):
     value=raw.get(key)
     if type(value) is not int or value<0:raise ValueError('Invalid official player '+key)
     values[key]=value
    if values['points']!=values['goals']+values['assists']:
     raise ValueError('Official player points identity mismatch')
    toi=raw.get('toi')
    played=None
    if isinstance(toi,str) and ':' in toi:
     parts=toi.split(':')
     if len(parts)!=2 or not all(part.isdigit() for part in parts) or int(parts[1])>=60:
      raise ValueError('Invalid official player TOI')
     played=(int(parts[0])*60+int(parts[1]))>0
    name=raw.get('name')
    if isinstance(name,dict):name=name.get('default') or ' '.join(x for x in (name.get('first'),name.get('last')) if x)
    players[str(pid)]={'player_id':pid,'name':str(name or ''),'position':raw.get('position') or raw.get('positionCode'),
                       **values,'toi':toi,'played':played}
  teams[side]=players
  goalie_rows=entry.get('goalies',[])
  if not isinstance(goalie_rows,list):raise ValueError('Official goalie rows missing')
  confirmed=[g.get('playerId') for g in goalie_rows if g.get('starter') is True and type(g.get('playerId')) is int]
  starters[side]=confirmed[0] if len(confirmed)==1 else None
 return {'teams':teams,'starters':starters}


def load_player_prop_forecasts(repo, day):
 root=Path(repo)/'frontend/data/nhl-player-props-forecasts'
 selected={};errors={}
 for path in sorted(root.glob('*.json')) if root.exists() else []:
  try:
   envelope=read(path);stored=envelope.get('sha256')
   body={k:v for k,v in envelope.items() if k!='sha256'}
   if local_day(envelope['start_utc'])!=day:continue
   if not stored or digest(body)!=stored:raise ValueError('Frozen player forecast hash mismatch')
   if envelope.get('kind')!='nhl_player_props_forecast_v1':raise ValueError('Unsupported player forecast kind')
   if str(envelope.get('game_id'))!=path.stem:raise ValueError('Forecast filename/game mismatch')
   if _utc(envelope['captured_at_utc'])>=_utc(envelope['start_utc']):raise ValueError('Player forecast captured at or after puck drop')
   if envelope.get('official') is not False or envelope.get('calibrated') is not False:raise ValueError('Player forecast marked official/calibrated')
   selected[str(envelope['game_id'])]=envelope
  except Exception as exc:
   errors[path.name]=type(exc).__name__+': '+str(exc)[:160]
 return selected,errors


def _utc(value):
 parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if parsed.tzinfo is None:raise ValueError('Timestamp must include timezone')
 return parsed.astimezone(timezone.utc)


def player_props_postmortem(forecasts, actual_by_game, source_errors):
 rows=[]
 metrics_by_stat=defaultdict(list);metrics_by_event=defaultdict(list)
 for gid,envelope in sorted(forecasts.items()):
  actual_game=actual_by_game.get(gid)
  actual_teams=(actual_game or {}).get('teams',{})
  starter_ids=(actual_game or {}).get('starters',{})
  scenarios=envelope.get('scenarios',[])
  matched=None
  if all(starter_ids.get(side) is not None for side in ('home','away')):
   for scenario in scenarios:
    hg=scenario.get('home_goalie') or {};ag=scenario.get('away_goalie') or {}
    if str(hg.get('id'))==str(starter_ids['home']) and str(ag.get('id'))==str(starter_ids['away']):
     matched=scenario;break
  for team,players in sorted(envelope.get('players',{}).items()):
   side='home' if team==envelope.get('home') else 'away' if team==envelope.get('away') else None
   if side is None:raise ValueError('Player forecast team is outside game')
   actuals=actual_teams.get(side,{})
   selected_probabilities={}
   probability_scenarios=[]
   for scenario in scenarios:
    by_team=(scenario.get('player_probabilities') or {}).get(team,[])
    if not isinstance(by_team,list):continue
    goalies={'home':scenario.get('home_goalie'),'away':scenario.get('away_goalie')}
    for item in by_team:
     selected_probabilities.setdefault(str(item.get('player_id')),[]).append({
      'home_goalie':goalies['home'],'away_goalie':goalies['away'],
      'weight':scenario.get('scenario_weight'),'expected':item.get('expected'),
      'probability':item.get('probability')})
   chosen_players={}
   if matched:
    chosen_players={str(item.get('player_id')):item for item in
     ((matched.get('player_probabilities') or {}).get(team,[]) or [])}
   for player in players:
    pid=str(player.get('player_id'))
    observed=actuals.get(pid)
    actual=None if observed is None else {k:observed[k] for k in ('goals','assists','points')}
    participation='boxscore_unavailable' if actual_game is None else (
     'not_in_boxscore' if observed is None else 'played' if observed.get('played') is True else
     'did_not_play' if observed.get('played') is False else 'participation_unconfirmed')
    probability_item=chosen_players.get(pid)
    probabilities=(probability_item or {}).get('probability')
    projected=(probability_item or {}).get('expected') or player.get('projected')
    projection_basis='matched_goalie_scenario' if probability_item else 'player_deployment_baseline'
    row={'game_id':gid,'home':envelope['home'],'away':envelope['away'],'start_utc':envelope['start_utc'],
     'forecast_run_id':envelope.get('run_id'),'forecast_as_of_utc':envelope['captured_at_utc'],
     'model_version':envelope.get('model_version'),'team':team,'player_id':player.get('player_id'),
     'player':player.get('name'),'position':player.get('position'),'line':player.get('line'),
     'participation':participation,'projection_basis':projection_basis,'projected':projected,'actual':actual,
     'probabilities':(probability_item or {}).get('probability'),'scenario_probabilities':selected_probabilities.get(pid,[]),
     'scenario_status':'matched_to_official_starters' if matched else 'official_starter_scenario_unresolved',
     'forecast_sha256':envelope['sha256']}
    rows.append(row)
    if participation=='played' and projected and actual:
     for stat in ('goals','assists','points'):
      if type(projected.get(stat)) in (int,float) and math.isfinite(projected[stat]):
       metrics_by_stat[(projection_basis,stat)].append((float(projected[stat]),actual[stat]))
     if probabilities:
      for event,stat in (('goal_at_least_one','goals'),('assist_at_least_one','assists'),('point_at_least_one','points')):
       probability=probabilities.get(event)
       if type(probability) in (int,float) and math.isfinite(probability) and 0<=probability<=1:
        metrics_by_event[event].append((float(probability),int(actual[stat]>=1)))
 metrics=[]
 for (basis,stat),values in sorted(metrics_by_stat.items()):
  metrics.append({'type':'count','stat':stat,'projection_basis':basis,'n':len(values),
   'mae':round(sum(abs(pred-actual) for pred,actual in values)/len(values),6),
   'bias_predicted_minus_actual':round(sum(pred-actual for pred,actual in values)/len(values),6),
   'predicted_total':round(sum(pred for pred,_ in values),6),'actual_total':sum(actual for _,actual in values)})
 for event,values in sorted(metrics_by_event.items()):
  metrics.append({'type':'probability_ge1','event':event,'n':len(values),
   'brier':round(sum((pred-actual)**2 for pred,actual in values)/len(values),6)})
 graded_games=sorted({r['game_id'] for r in rows if r['participation']=='played'})
 return {'kind':'nhl_player_props_postmortem_v1',
  'status':'complete' if forecasts and not source_errors and len(graded_games)==len(forecasts) else
   'partial' if forecasts else 'no_frozen_player_forecasts',
  'forecast_games':len(forecasts),'graded_games':len(graded_games),
  'forecast_players':len(rows),'graded_players':sum(r['participation']=='played' for r in rows),
  'selection_policy':'latest valid pregame player forecast captured before puck drop; postgame revisions are rejected',
  'scenario_policy':'grade scenario probabilities only when both official starters match a recorded goalie scenario; otherwise retain alternatives without blending them',
  'metrics':metrics,'players':rows,'source_errors':source_errors,
  'automatic_parameter_updates':False,'calibration_status':'observations_only_pending_independent_validation',
  'limitations':['Players absent from the official boxscore are not assigned zero statistics.',
   'DNP rows are excluded from accuracy metrics.','Unmatched goalie scenarios are retained but not averaged.']}


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
 chosen,paths,total=original_forecasts(repo,day);player_forecasts,player_forecast_errors=load_player_prop_forecasts(repo,day);sources={};errors={};player_errors=dict(player_forecast_errors);player_boxscores={};score_games={}
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
  if gid not in expected and gid not in player_forecasts:continue
  url=BASE+'gamecenter/'+gid+'/play-by-play'
  try:
   if parse_utc(game['startTimeUTC'])>=now:raise ValueError('Final reported before game start')
   value=checked_label(capture(url),game)
   if value is None:pending.append(gid)
   else:
    labels[gid]=value
    if gid in player_forecasts:
     box_url=BASE+'gamecenter/'+gid+'/boxscore'
     try:player_boxscores[gid]=official_player_boxscore(capture(box_url),gid,game)
     except Exception as player_exc:player_errors[gid]=type(player_exc).__name__+': '+str(player_exc)[:160]
  except Exception as exc:errors[url]=type(exc).__name__+': '+str(exc)[:160]
 rows=[];grouped=defaultdict(list)
 for key,envelope in sorted(chosen.items()):
  gid,model,market=key;r=envelope['record'];label=labels.get(gid)
  if not label:continue
  if any(r[k]!=label[k] for k in ('home','away')) or r['start_utc']!=score_games[gid]['startTimeUTC']:raise ValueError('Forecast/result identity mismatch')
  target={'ml':label['ml_winner'],'rt':label['rt_result'],'first3':label['first_to_plus3'] or 'none','home3':'yes' if label['home_reached_plus3'] else 'no','away3':'yes' if label['away_reached_plus3'] else 'no'}[market]
  probabilities=r['probabilities'];modal=max(probabilities,key=probabilities.get)
  source_classification=r.get('forecast_source_classification') or 'verified_legacy_frozen_ledger'
  source_verified=r.get('point_in_time_sources_verified') is True
  row={'game_id':gid,'model_version':model,'market':market,'probabilities':probabilities,'actual':target,'modal_class':modal,'modal_correct':modal==target,
   'brier':brier([probabilities[c] for c in CATEGORIES[market]],target,CATEGORIES[market]),'log_loss':-math.log(max(1e-12,probabilities[target])),
   'prediction_as_of_utc':r['prediction_as_of_utc'],'source_path':paths[key],'forecast_sha256':envelope['sha256'],
   'source_classification':source_classification,'point_in_time_sources_verified':source_verified,
   'source_archive_content_sha256':envelope.get('archive_content_sha256'),'source_output_sha256':envelope.get('source_output_sha256')}
  rows.append(row);grouped[(model,market,source_classification,source_verified)].append(row)
 metrics=[{'model_version':model,'market':market,'source_classification':source_classification,'point_in_time_sources_verified':source_verified,
   'n':len(v),'modal_correct':sum(r['modal_correct'] for r in v),'brier':round(sum(r['brier'] for r in v)/len(v),6),
   'log_loss':round(sum(r['log_loss'] for r in v)/len(v),6)}
   for (model,market,source_classification,source_verified),v in sorted(grouped.items())]
 player_props=player_props_postmortem(player_forecasts,player_boxscores,player_errors)
 games=[{'game_id':gid,'home':g['homeTeam']['abbrev'],'away':g['awayTeam']['abbrev'],'start_utc':g['startTimeUTC'],'state':g['gameState'],
  'home_score':g['homeTeam'].get('score') if g['gameState'] in ('OFF','FINAL') else None,'away_score':g['awayTeam'].get('score') if g['gameState'] in ('OFF','FINAL') else None,
  'prediction_available':gid in expected,'outcomes':labels.get(gid)} for gid,g in sorted(score_games.items())]
 verified_expected={str(k[0]) for k,envelope in chosen.items() if envelope['record'].get('point_in_time_sources_verified') is True}
 baseline={gid:{'model':r['record']['model_version'],'home':r['record']['home'],'away':r['record']['away'],'start_utc':r['record']['start_utc'],'as_of':r['record']['prediction_as_of_utc'],'p_home':r['record']['probabilities']['home']} for (gid,model,market),r in chosen.items() if market=='ml' and r['record'].get('point_in_time_sources_verified') is True}
 paired=None
 if baseline and len({k[1] for k in chosen if k[2]=='ml' and str(k[0]) in verified_expected})==1:
  challenger={gid:r for gid,r in collect_challenger((Path(repo)/'frontend/data/nhl-shadow').glob('run-*/shadow.json')).items() if gid in verified_expected}
  paired=paired_evaluate(baseline,challenger,final_scores({'games':[g for gid,g in score_games.items() if gid in labels]}))
 unverified_count=sum(1 for envelope in chosen.values() if envelope['record'].get('point_in_time_sources_verified') is not True)
 source_warnings=['One or more immutable archived forecasts have no independent point-in-time source verification; their scores are descriptive and excluded from paired model comparison.'] if unverified_count else []
 status='needs_review' if errors or source_warnings else 'pending_results' if pending else 'complete' if chosen else 'no_forecasts'
 core={'kind':'nhl_daily_postmortem','date':day,'timezone':'America/Santiago','pipeline_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'status':status,'complete':not errors and not pending and not source_warnings,
  'official_games':len(games),'forecast_games':len(expected),'graded_games':len(labels),'market_forecasts_scored':len(rows),'player_props':player_props,'unpredicted_games':sorted(set(score_games)-expected),
  'source_forecast_files':total,'unique_forecast_issuances':len(chosen),'unverified_forecast_count':unverified_count,'source_warnings':source_warnings,
  'selection_policy':'earliest valid pregame issuance per game/model/market',
  'pending_game_ids':pending,'source_errors':errors,'games':games,'market_scores':rows,'metrics':metrics,'paired_ml_comparison':paired,
  'source_hashes':{url:digest(payload) for url,payload in sorted(sources.items())},'automatic_promotion':False,'parameters_changed':False,
  'learning_state':'observations_only_pending_independent_validation','limitations':['Markets from the same game are correlated.','No parameter changes or promotion from daily results.','Archive hashes verify stored forecast content; they do not independently validate captured pregame input provenance.','Descriptive scores from unverified archived forecasts are excluded from certification and paired comparison.']}
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
  write(archive/'report.json',report);write(archive/'selected-forecasts.json',forecasts);write(archive/'selected-player-props.json',core.get('player_props',{}))
  for url,payload in sources.items():
   name=digest(url)+'.json.gz';data=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();path=archive/'evidence'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(data,mtime=0))
  observations=[g['outcomes'] for g in core['games'] if g.get('outcomes')]
  learning={'kind':'nhl_postgame_learning','date':day,'available_at_utc':now.isoformat(),'report_revision':revision,'data_class':'POSTGAME_LABELS_NOT_PREGAME_FEATURES','observations':observations,'player_prop_observation_count':core.get('player_props',{}).get('graded_players',0),
   'player_prop_metrics':core.get('player_props',{}).get('metrics',[]),
   'signals':[{'type':'both_sides_reached_plus3','game_id':g['game_id']} for g in observations if g['home_reached_plus3'] and g['away_reached_plus3']],
   'state':'quarantined_for_future_chronological_training','applied_to_live_parameters':False,'automatic_promotion':False,'next_step':'Validate hypotheses on untouched future data; daily outcomes alone never authorize parameter updates.'}
  write(archive/'learning.json',learning)
 write(public,report);write(repo/'nhl/learning/postmortems'/(day+'.json'),read(archive/'learning.json'))
 return {'date':day,'status':report['status'],'revision':revision,'graded_games':report['graded_games'],'source_errors':report['source_errors']}

def update_index(repo):
 repo=Path(repo);reports=[read(p) for p in sorted((repo/'frontend/data/nhl-postmortems').glob('*.json'))]
 summary={'kind':'nhl_postmortem_index','automatic_parameter_updates':False,'days':[{**{k:r[k] for k in ('date','status','complete','official_games','forecast_games','graded_games','market_forecasts_scored','metrics','revision_sha256','generated_at_utc')},'player_props':{k:r.get('player_props',{}).get(k) for k in ('status','forecast_games','graded_games','forecast_players','graded_players','metrics')}} for r in reports]}
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
