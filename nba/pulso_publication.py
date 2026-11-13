"""Publish NBA baseline plus a separately labeled injury research scenario."""
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def build(snapshot,run_id,module_context=None,injury_adjustment=None,travel_adjustment=None,matchup_adjustment=None,player_stat_projections=None):
 body={k:v for k,v in snapshot.items() if k!='content_sha256'}
 snapshot_digest=digest(body)
 if snapshot.get('content_sha256')!=snapshot_digest:raise ValueError('Snapshot digest mismatch')
 at=datetime.fromisoformat(snapshot['created_at_utc'].replace('Z','+00:00'));seen=set()
 if at.tzinfo is None:raise ValueError('Missing timestamp timezone')
 module_context=module_context or {}
 if module_context and module_context.get('snapshot_sha256')!=snapshot_digest:raise ValueError('Module context / snapshot mismatch')
 if module_context:
  module_body={k:v for k,v in module_context.items() if k!='content_sha256'}
  if module_context.get('content_sha256')!=digest(module_body):raise ValueError('Module context digest mismatch')
 module_games=module_context.get('games',{})
 adjustment_games={}
 if injury_adjustment:
  adjustment_body={k:v for k,v in injury_adjustment.items() if k!='content_sha256'}
  if injury_adjustment.get('content_sha256')!=digest(adjustment_body):raise ValueError('Injury adjustment digest mismatch')
  if injury_adjustment.get('snapshot_sha256')!=snapshot_digest:raise ValueError('Injury adjustment / snapshot mismatch')
  if injury_adjustment.get('calibrated') is not False or injury_adjustment.get('production_approved') is not False:
   raise ValueError('Research injury scenario must stay uncalibrated and unapproved')
  adjustment_games={str(row['game_id']):row for row in injury_adjustment.get('games',[])}
  if len(adjustment_games)!=len(injury_adjustment.get('games',[])) or set(adjustment_games)!={str(row['game_id']) for row in snapshot['predictions']}:
   raise ValueError('Injury adjustment must cover the full slate exactly')
 travel_games={}
 if travel_adjustment:
  travel_body={k:v for k,v in travel_adjustment.items() if k!='content_sha256'}
  if travel_adjustment.get('content_sha256')!=digest(travel_body):raise ValueError('Travel adjustment digest mismatch')
  if travel_adjustment.get('snapshot_sha256')!=snapshot_digest:raise ValueError('Travel adjustment / snapshot mismatch')
  if travel_adjustment.get('calibrated') is not False or travel_adjustment.get('production_approved') is not False:
   raise ValueError('Research travel scenario must stay uncalibrated and unapproved')
  travel_games={str(row['game_id']):row for row in travel_adjustment.get('games',[])}
  if len(travel_games)!=len(travel_adjustment.get('games',[])) or set(travel_games)!={str(row['game_id']) for row in snapshot['predictions']}:
   raise ValueError('Travel adjustment must cover the full slate exactly')
 matchup_games={}
 if matchup_adjustment:
  matchup_body={k:v for k,v in matchup_adjustment.items() if k!='content_sha256'}
  if matchup_adjustment.get('content_sha256')!=digest(matchup_body):raise ValueError('Matchup adjustment digest mismatch')
  if matchup_adjustment.get('snapshot_sha256')!=snapshot_digest:raise ValueError('Matchup adjustment / snapshot mismatch')
  if matchup_adjustment.get('calibrated') is not False or matchup_adjustment.get('production_approved') is not False:
   raise ValueError('Research matchup scenario must stay uncalibrated and unapproved')
  matchup_games={str(row['game_id']):row for row in matchup_adjustment.get('games',[])}
  if len(matchup_games)!=len(matchup_adjustment.get('games',[])) or set(matchup_games)!={str(row['game_id']) for row in snapshot['predictions']}:
   raise ValueError('Matchup adjustment must cover the full slate exactly')
 player_stat_games={}
 if player_stat_projections:
  projection_body={k:v for k,v in player_stat_projections.items() if k!='content_sha256'}
  if player_stat_projections.get('content_sha256')!=digest(projection_body):raise ValueError('Player stat projections digest mismatch')
  if player_stat_projections.get('snapshot_sha256')!=snapshot_digest:raise ValueError('Player stat projections / snapshot mismatch')
  if player_stat_projections.get('calibrated') is not False or player_stat_projections.get('probabilities_adjusted') is not False:
   raise ValueError('Player stat projections must remain descriptive and not alter win probabilities')
  player_stat_games=player_stat_projections.get('games',{})
  if set(player_stat_games)!={str(row['game_id']) for row in snapshot['predictions']}:
   raise ValueError('Player stat projections must cover the full slate')
 for row in snapshot['predictions']:
  gid=str(row['game_id']);start=datetime.fromisoformat(row['tipoff_utc'].replace('Z','+00:00'))
  if gid in seen or start<=at or row['home_team']==row['away_team']:raise ValueError('Invalid pregame fixture')
  seen.add(gid)
  for key in ('elo_p_home','challenger_p_home','hybrid_p_home'):
   p=row[key]
   if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1:raise ValueError('Invalid probability')
 predictions=[]
 for row in snapshot['predictions']:
  gid=str(row['game_id']);copy=dict(row)
  baseline=row['hybrid_p_home']
  modules=json.loads(json.dumps(module_games.get(gid,{}))) if module_context else {}
  candidate=adjustment_games.get(gid)
  official_candidate=candidate
  selected_secondary=False
  if candidate:
   secondary=candidate.get('multi_source_scenario')
   if (isinstance(secondary,dict) and secondary.get('status')=='research_scenario'
       and secondary.get('secondary_consensus_out_count',0)>0):
    candidate=secondary
    selected_secondary=True
  model_home=baseline
  injury_applied=False;travel_applied=False;matchup_applied=False
  travel=travel_games.get(gid)
  matchup=matchup_games.get(gid)
  if candidate:
   if not math.isclose(candidate.get('base_home_probability',-1),baseline,rel_tol=0,abs_tol=1e-12):
    raise ValueError('Injury scenario baseline differs from frozen forecast')
   copy['injury_probability_scenario']=candidate
   if selected_secondary:copy['official_only_injury_scenario']=official_candidate
   copy['statistical_baseline_p_home']=baseline
   copy['statistical_baseline_p_away']=1.0-baseline
   if candidate.get('status')=='research_scenario':
    home=candidate.get('injury_adjusted_home_probability');away=candidate.get('injury_adjusted_away_probability')
    if (type(home) not in (int,float) or type(away) not in (int,float)
        or not math.isfinite(home) or not math.isfinite(away)
        or not 0<home<1 or not 0<away<1 or not math.isclose(home+away,1,rel_tol=0,abs_tol=1e-10)):
     raise ValueError('Invalid injury research probability')
    model_home=home;injury_applied=True
    official_used=(candidate.get('official_out_count',0)>0 or any(
     team.get('official_out_count',0)>0 for team in candidate.get('teams',{}).values()))
    secondary_used=candidate.get('secondary_consensus_out_count',0)>0
    for key in ('official_injury_report','injury_source_reconciliation','rotation_minutes','availability_impact'):
     module=modules.get(key)
     if not isinstance(module,dict):continue
     if key=='official_injury_report':
      module['affects_prediction']=official_used;module['entered_prediction']=official_used
      if official_used:
       module['status']='research_scenario'
       module['detail']='Bajas OUT del informe oficial entran en el escenario experimental de minutos y producción.'
     elif key=='injury_source_reconciliation':
      module['affects_prediction']=secondary_used;module['entered_prediction']=secondary_used
      if secondary_used:
       module['status']='research_scenario'
       module['detail']='Bajas OUT con identidad validada y acuerdo entre CBS Sports y ESPN entran en el escenario experimental.'
     else:
      module['status']='research_scenario';module['affects_prediction']=True;module['entered_prediction']=True
      module['detail']='La disponibilidad, minutos redistribuidos y producción histórica modifican este candidato; escenario experimental no calibrado.'
    lineup_used=any(type(team.get('lineup_role_weights_applied')) is int and team.get('lineup_role_weights_applied')>0 for team in candidate.get('teams',{}).values())
    if lineup_used:
     module=modules.get('starting_lineups')
     if isinstance(module,dict):
      module['status']='research_scenario';module['affects_prediction']=True;module['entered_prediction']=True
      module['detail']='El quinteto RotoWire, observado antes del partido, cambia el reparto de minutos usando el historial de cada jugador cuando fue titular; efecto experimental.'
  if matchup:
   if not math.isclose(matchup.get('base_home_probability',-1),baseline,rel_tol=0,abs_tol=1e-12):
    raise ValueError('Matchup scenario baseline differs from frozen forecast')
   copy['player_matchup_probability_scenario']=matchup
   if matchup.get('status')=='research_scenario' and matchup.get('applied') is True:
    delta=matchup.get('log_odds_delta')
    expected=matchup.get('adjusted_home_probability')
    standalone=1.0/(1.0+math.exp(-(math.log(baseline/(1.0-baseline))+delta))) if type(delta) in (int,float) and abs(delta)<=0.15 else None
    if (standalone is None or type(expected) not in (int,float) or not math.isfinite(expected)
        or not 0<expected<1 or not math.isclose(standalone,expected,rel_tol=0,abs_tol=1e-8)):
     raise ValueError('Invalid bounded matchup research probability')
    prior_model_home=model_home
    model_home=1.0/(1.0+math.exp(-(math.log(prior_model_home/(1.0-prior_model_home))+delta)))
    matchup_applied=not math.isclose(model_home,prior_model_home,rel_tol=0,abs_tol=1e-12)
    module=modules.get('player_matchups')
    if isinstance(module,dict):
     module['status']='research_scenario';module['affects_prediction']=matchup_applied;module['entered_prediction']=matchup_applied
     module['detail']='El historial de cruces atacante-defensor y el quinteto por posición modifican este candidato; la asignación futura es estimada, no confirmada, y sigue experimental.'
  if travel:
   copy['travel_probability_scenario']=travel
   if travel.get('status')=='research_scenario' and travel.get('applied') is True:
    delta=travel.get('log_odds_delta')
    if type(delta) not in (int,float) or not math.isfinite(delta) or abs(delta)>0.2:
     raise ValueError('Invalid bounded travel log-odds adjustment')
    prior_model_home=model_home
    model_home=1.0/(1.0+math.exp(-(math.log(prior_model_home/(1.0-prior_model_home))+delta)))
    travel_applied=not math.isclose(model_home,prior_model_home,rel_tol=0,abs_tol=1e-12)
    module=modules.get('travel_time_zones')
    if isinstance(module,dict):
     module['status']='research_scenario';module['affects_prediction']=travel_applied;module['entered_prediction']=travel_applied
     module['detail']='El viaje y el cambio horario modifican este candidato porque el ajuste superó una validación cronológica separada; sigue experimental.'
  if candidate or travel or matchup:
   copy['model_p_home']=model_home
   copy['model_p_away']=1.0-model_home
   applied=[name for name,used in (('injury',injury_applied),('matchup',matchup_applied),('travel',travel_applied)) if used]
   status_by_source={'injury':'injury_adjusted_research_candidate','matchup':'matchup_adjusted_research_candidate','travel':'travel_adjusted_research_candidate'}
   copy['model_probability_status']=status_by_source[applied[0]] if len(applied)==1 else 'combined_research_candidate' if applied else 'baseline_only'
   copy['probability_adjustments_applied']=applied
   copy['model_probability_calibrated']=False
  if player_stat_projections:copy['player_stat_projections']=player_stat_games[gid]
  if module_context:copy['supporting_modules']=modules
  predictions.append(copy)
 research_count=sum(row.get('model_probability_status') in ('injury_adjusted_research_candidate','matchup_adjusted_research_candidate','travel_adjusted_research_candidate','combined_research_candidate') for row in predictions)
 return dict(kind='nba_pulso_research_publication_v1',run_id=str(run_id),snapshot_sha256=snapshot_digest,created_at_utc=snapshot['created_at_utc'],predictions=predictions,calibrated=False,availability_and_lineups_included=bool(module_context),modules_change_probabilities=research_count>0,research_scenarios_affect_probabilities=research_count,source='frozen_nba_prospective_snapshot')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',required=True);p.add_argument('--module-context');p.add_argument('--injury-adjustment');p.add_argument('--travel-adjustment');p.add_argument('--matchup-adjustment');p.add_argument('--player-stat-projections');a=p.parse_args();out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);context=json.loads(Path(a.module_context).read_text()) if a.module_context else None;adjustment=json.loads(Path(a.injury_adjustment).read_text()) if a.injury_adjustment else None;travel=json.loads(Path(a.travel_adjustment).read_text()) if a.travel_adjustment else None;matchup=json.loads(Path(a.matchup_adjustment).read_text()) if a.matchup_adjustment else None;stats=json.loads(Path(a.player_stat_projections).read_text()) if a.player_stat_projections else None;out.write_text(json.dumps(build(json.loads(Path(a.snapshot).read_text()),a.run_id,context,adjustment,travel,matchup,stats),indent=2,allow_nan=False))
