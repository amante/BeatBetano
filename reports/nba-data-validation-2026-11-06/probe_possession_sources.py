import sys,json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import requests
sys.path.insert(0,'nba')
from verifiable_capture import save_new
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True)
root=Path(parser.parse_args().output)
root.mkdir(parents=True,exist_ok=False)
# Field list from public OpenAPI schema, no market/probability fields retained.
fields=('EndTime','Events','FG2A','FG2M','FG3A','FG3M','GameDate','GameId',
        'NonShootingFoulsThatResultedInFts','OffensiveRebounds','Opponent','Period',
        'ShootingFoulsDrawn','StartScoreDifferential','StartTime','StartType','Turnovers')
def one(item):
 team,tid=item
 url='https://api.pbpstats.com/get-possessions/nba'
 params={'Season':'2026-27','SeasonType':'Regular Season','TeamId':tid,
         'FromDate':'2026-11-05','ToDate':'2026-11-05','OffDef':'Offense'}
 result={'team':team,'source_url':url,'parameters':params,
         'requested_at_utc':datetime.now(timezone.utc).isoformat(),
         'status':'unavailable','normalized_model_contract_ready':False}
 try:
  r=requests.get(url,params=params,timeout=(8,18));result['http_status']=r.status_code;r.raise_for_status()
  payload=r.json();rows=payload['possessions']
  if not isinstance(rows,list):raise ValueError('Invalid possessions list')
  filtered=[{k:p[k] for k in fields if k in p} for p in rows]
  result.update(status='observed_source_rows_only' if rows else 'no_rows',rows=len(rows),
                possibly_truncated=len(rows)>=500,game_ids=sorted({str(p['GameId']) for p in rows}))
  result['payload_sha256']=save_new(root,'pbpstats-'+team+'-possessions.json',{'possessions':filtered})
 except (requests.RequestException,ValueError,KeyError,TypeError) as e:
  result.update(error_type=type(e).__name__,detail=str(e)[:500])
 result['observed_at_utc']=datetime.now(timezone.utc).isoformat()
 return result
with ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(one,[('PHX','1610612756'),('ORL','1610612753'),('GSW','1610612744'),('MIA','1610612748')]))
report={'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'documentation_url':'https://api.pbpstats.com/docs','sources':results,
        'no_odds_input':True,'limitations':['Source rows do not yet reconcile full scoring including technical/free throws or verified lineup stints. They are not accepted engine possession inputs.', 'No source query uses leverage or market/probability filters. No automatic model promotion.']}
save_new(root,'possession-source-probes.json',report)
print(json.dumps([{k:v for k,v in r.items() if k in ('team','status','rows','error_type')} for r in results]))
