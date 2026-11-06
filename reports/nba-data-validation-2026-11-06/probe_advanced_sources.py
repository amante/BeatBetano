import sys,json,hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import requests
sys.path.insert(0,'nba')
from nba_official_pace_capture import collect,HEADERS
from postmortem_engine import no_market_fields
from verifiable_capture import save_new
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True)
root=Path(parser.parse_args().output)
root.mkdir(parents=True,exist_ok=False)
base={'Season':'2026-27','SeasonType':'Regular Season','MeasureType':'Advanced',
      'PerMode':'Totals','DateFrom':'','DateTo':'11/05/2026','LastNGames':0,
      'LeagueID':'00','Month':0,'OpponentTeamID':0,'TeamID':0,
      'PlusMinus':'N','PaceAdjust':'N','Rank':'N'}
def probe(item):
 name,endpoint,extra=item
 url='https://stats.nba.com/stats/'+endpoint
 params={**base,**extra}
 result={'source_url':url,'parameters':params,'requested_at_utc':datetime.now(timezone.utc).isoformat(),
         'status':'unavailable','adjusted_player_effects_available':False}
 try:
  r=requests.get(url,params=params,headers=HEADERS,timeout=(8,18))
  result['http_status']=r.status_code
  r.raise_for_status()
  payload=r.json();no_market_fields(payload)
  sets=payload.get('resultSets',[])
  if not sets:raise ValueError('Missing resultSets')
  result.update(status='observed_raw_statistics_only',result_sets=[{'name':v.get('name'),'rows':len(v.get('rowSet',[])),'headers':v.get('headers',[])} for v in sets])
  result['payload_sha256']=save_new(root,name+'-payload.json',payload)
 except (requests.RequestException,ValueError,KeyError,TypeError) as e:
  result.update(error_type=type(e).__name__,detail=str(e)[:500])
 result['observed_at_utc']=datetime.now(timezone.utc).isoformat()
 return name,result
items=[('player-advanced','leaguedashplayerstats',{'College':'','Conference':'','Country':'','Division':'','DraftPick':'','DraftYear':'','GameScope':'','GameSegment':'','Height':'','Location':'','Outcome':'','PORound':0,'Period':0,'PlayerExperience':'','PlayerPosition':'','SeasonSegment':'','ShotClockRange':'','StarterBench':'','VsConference':'','VsDivision':'','Weight':''}),('player-on-off','teamplayeronoffsummary',{'TeamID':1610612756})]
with ThreadPoolExecutor(max_workers=3) as pool:
 futures=[pool.submit(probe,i) for i in items]
 pace=pool.submit(collect,'2026-11-06')
 results=dict(f.result() for f in futures)
 results['team-advanced']=pace.result()
report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'sources':results,
        'no_odds_input':True,'note':'Connectivity smoke tests only. PHX raw on/off is not opponent-adjusted impact and cannot populate the model contract. No retries or access bypass.'}
save_new(root,'advanced-source-probes.json',report)
print(json.dumps({k:v['status'] for k,v in results.items()}))
