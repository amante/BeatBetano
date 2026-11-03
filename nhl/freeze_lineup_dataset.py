"""Immutable source-linked lineup research records; no retrospective lineups."""
import argparse,gzip,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from nhl.pulso_pregame_v7 import parse_utc

def freeze(directory,destination,run_id):
 if not str(run_id).isdigit():raise ValueError('Numeric run ID required')
 root=Path(directory);names=['report.json','skater_history.json','prior_lineup_reference.json','lineup_changes.json','lineup_features.json','skater_history.sources.json.gz','prior_lineup_reference.sources.json.gz']
 blobs={n:(root/n).read_bytes() for n in names};read=lambda n:json.loads(blobs[n]);report=read('report.json');features=read('lineup_features.json')
 if report.get('data_kind')!='source_readiness_only' or features.get('kind')!='nhl_lineup_feature_packet_v1':raise ValueError('Invalid research inputs')
 at=datetime.now(timezone.utc);fixtures={str(g['game_id']):g for g in report['games']};records=[]
 for game in features['games']:
  fixture=fixtures[str(game['game_id'])]
  if at>=parse_utc(fixture['start_utc']):continue
  sides=game['teams'];ready=all(sides.get(t,{}).get('status')=='descriptive_features_only' and all(sides[t]['groups'][k]['complete'] for k in ('projected_players','out_of_projection','new_in_projection')) for t in (fixture['home'],fixture['away']))
  records.append(dict(game_id=str(game['game_id']),home=fixture['home'],away=fixture['away'],start_utc=fixture['start_utc'],frozen_at_utc=at.isoformat(),teams=sides,complete_observed_inputs=ready,training_approved=False))
 result=dict(kind='nhl_frozen_lineup_dataset_v1',run_id=str(run_id),frozen_at_utc=at.isoformat(),records=records,source_sha256={n:hashlib.sha256(b).hexdigest() for n,b in blobs.items()},probabilities_modified=False,limitations=['Complete inputs do not certify calibration or causal impact.','No labels or postgame participant lists are substituted for pregame projections.'])
 out=Path(destination);out.parent.mkdir(parents=True,exist_ok=True);bundle=out.with_suffix('.sources.json.gz')
 if out.exists() or bundle.exists():raise FileExistsError('Frozen run already exists')
 with out.open('x') as f:json.dump(result,f,indent=2)
 with bundle.open('xb') as f:f.write(gzip.compress(json.dumps({n:b.hex() for n,b in blobs.items()}).encode(),mtime=0))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--destination',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();freeze(a.directory,a.destination,a.run_id)
