"""Publish NBA baseline plus a separately labeled injury research scenario."""
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def build(snapshot,run_id,module_context=None,injury_adjustment=None):
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
  model_home=baseline
  if candidate:
   if not math.isclose(candidate.get('base_home_probability',-1),baseline,rel_tol=0,abs_tol=1e-12):
    raise ValueError('Injury scenario baseline differs from frozen forecast')
   copy['injury_probability_scenario']=candidate
   copy['statistical_baseline_p_home']=baseline
   copy['statistical_baseline_p_away']=1.0-baseline
   if candidate.get('status')=='research_scenario':
    home=candidate.get('injury_adjusted_home_probability');away=candidate.get('injury_adjusted_away_probability')
    if (type(home) not in (int,float) or type(away) not in (int,float)
        or not math.isfinite(home) or not math.isfinite(away)
        or not 0<home<1 or not 0<away<1 or not math.isclose(home+away,1,rel_tol=0,abs_tol=1e-10)):
     raise ValueError('Invalid injury research probability')
    model_home=home
    for key in ('official_injury_report','rotation_minutes','availability_impact'):
     module=modules.get(key)
     if isinstance(module,dict):
      module['status']='research_scenario';module['affects_prediction']=True;module['entered_prediction']=True
      module['detail']='Cambia el porcentaje del candidato NBA mediante bajas oficiales, minutos redistribuidos y producción histórica; escenario experimental no calibrado.'
  copy['model_p_home']=model_home
  copy['model_p_away']=1.0-model_home
  copy['model_probability_status']='injury_adjusted_research_candidate' if candidate and candidate.get('status')=='research_scenario' else 'baseline_only'
  copy['model_probability_calibrated']=False
  if module_context:copy['supporting_modules']=modules
  predictions.append(copy)
 research_count=sum(row.get('model_probability_status')=='injury_adjusted_research_candidate' for row in predictions)
 return dict(kind='nba_pulso_research_publication_v1',run_id=str(run_id),snapshot_sha256=snapshot_digest,created_at_utc=snapshot['created_at_utc'],predictions=predictions,calibrated=False,availability_and_lineups_included=bool(module_context),modules_change_probabilities=research_count>0,research_scenarios_affect_probabilities=research_count,source='frozen_nba_prospective_snapshot')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',required=True);p.add_argument('--module-context');p.add_argument('--injury-adjustment');a=p.parse_args();out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);context=json.loads(Path(a.module_context).read_text()) if a.module_context else None;adjustment=json.loads(Path(a.injury_adjustment).read_text()) if a.injury_adjustment else None;out.write_text(json.dumps(build(json.loads(Path(a.snapshot).read_text()),a.run_id,context,adjustment),indent=2,allow_nan=False))
