"""Publish authenticated-by-digest research snapshots without changing model claims."""
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime

def build(snapshot,run_id):
 body={k:v for k,v in snapshot.items() if k!='content_sha256'}
 digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if snapshot.get('content_sha256')!=digest:raise ValueError('Snapshot digest mismatch')
 at=datetime.fromisoformat(snapshot['created_at_utc'].replace('Z','+00:00'));seen=set()
 if at.tzinfo is None:raise ValueError('Missing timestamp timezone')
 for row in snapshot['predictions']:
  gid=str(row['game_id']);start=datetime.fromisoformat(row['tipoff_utc'].replace('Z','+00:00'))
  if gid in seen or start<=at or row['home_team']==row['away_team']:raise ValueError('Invalid pregame fixture')
  seen.add(gid)
  for key in ('elo_p_home','challenger_p_home','hybrid_p_home'):
   p=row[key]
   if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1:raise ValueError('Invalid probability')
 return dict(kind='nba_pulso_research_publication_v1',run_id=str(run_id),snapshot_sha256=digest,created_at_utc=snapshot['created_at_utc'],predictions=snapshot['predictions'],calibrated=False,availability_and_lineups_included=False,source='frozen_nba_prospective_snapshot')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(build(json.loads(Path(a.snapshot).read_text()),a.run_id),indent=2))
