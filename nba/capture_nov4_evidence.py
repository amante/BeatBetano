import sys,json,hashlib,concurrent.futures,time
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
import requests
sys.path.insert(0,str(Path(__file__).resolve().parent))
from espn_games import parse_events,BASE
from clean_regular import clean
from current_feed import parse_current
from possession_intelligence import extract
from player_game_history import parse_boxscore
import argparse
parser=argparse.ArgumentParser(description='Reproduce the November 4 2026 research slate; never overwrite an archive.')
parser.add_argument('--output-dir',required=True)
args=parser.parse_args()
out=Path(args.output_dir);out.mkdir(exist_ok=True)
def now():return datetime.now(timezone.utc).isoformat()
def save(name,data):
 p=out/name
 with p.open('x') as f:json.dump(data,f,indent=2,allow_nan=False)
def get(url,params=None):
 for attempt in range(3):
  try:
   r=requests.get(url,params=params,timeout=25);r.raise_for_status();return r.json()
  except Exception:
   if attempt==2:raise
   time.sleep(1)
p=get(BASE,{'dates':'20261104','limit':500});t=now();schedule=parse_current(p,t)
save('scoreboard.json',schedule)
fixtures=[g for g in schedule['future_fixtures'] if not {'NY','NYK'}&{g['home_team'],g['away_team']}]
save('fixtures.json',fixtures)
print('fixtures',len(fixtures),flush=True)
windows=[('2023-10-24','2024-04-14'),('2024-10-22','2025-04-13'),('2025-10-21','2026-04-12'),('2026-10-20','2026-11-03')]
days=[]
for start,end in windows:
 d=date.fromisoformat(start)
 while d<=date.fromisoformat(end):days.append(d.isoformat());d+=timedelta(days=1)
def dayfetch(day):
 try:return day,parse_events(get(BASE,{'dates':day.replace('-',''),'limit':500})),None
 except Exception as e:return day,[],str(e)
rows=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for day,games,err in pool.map(dayfetch,days):
  rows+=games
  if err:errors.append({'date':day,'error':err})
print('scoreboards',len(rows),'errors',len(errors),flush=True)
byid={g['game_id']:g for g in rows};rows=sorted(byid.values(),key=lambda g:(g['tipoff_utc'],g['game_id']))
past=[g for g in rows if g['season']!=2027]
try:past,audit=clean(past)
except ValueError as e:past=[];audit={'coverage_verified':False,'error':str(e)}
current=[g for g in rows if g['season']==2027]
history=past+current
save('history.json',history);save('history_audit.json',{'observed_at_utc':now(),'source':BASE,'cleaning':audit,'errors':errors,'current_games':len(current),'history_games':len(history)})
print('clean history',len(history),flush=True)
def summary(g):
 try:
  p=get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary',{'event':g['game_id']});t=now()
  stats=extract(p,g);players=parse_boxscore(p,g,t)
  return {'game':g,'observed_at_utc':t,'team_statistics':stats,'players':players},None
 except Exception as e:return None,{'game_id':g['game_id'],'error':str(e)}
results=[];err=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 for row,e in pool.map(summary,current):
  if row:results.append(row)
  if e:err.append(e)
save('boxscores.json',{'source':'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary','games':results,'errors':err})
print('boxscores',len(results),'errors',len(err),flush=True)
