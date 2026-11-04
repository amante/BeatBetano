import sys,json,concurrent.futures
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prospective import generate
from espn_current_roster_feed import collect as rosters
from lineup_live_collector import collect as lineups
from official_injury_pdf import retrieve
from official_injury_table import extract
from sporting_feed import collect as sporting
from player_status_intake import reconcile
from active_roster_resolver import resolve
from rotation_efficiency_report import build as rotation
from joint_minutes_report import build as minutes
from availability_scenarios import scenarios
from reproducible_slate import build,markdown,digest
import argparse
parser=argparse.ArgumentParser(description='Reproduce the November 4 2026 research slate; never overwrite an archive.')
parser.add_argument('--output-dir',required=True)
args=parser.parse_args()
out=Path(args.output_dir)
read=lambda name:json.loads((out/name).read_text())
def save(name,data):
 with (out/name).open('x') as f:json.dump(data,f,indent=2,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()
fixtures=read('fixtures.json');history=read('history.json');box=read('boxscores.json')
audit=read('history_audit.json')
if not audit['cleaning'].get('coverage_verified') or audit['errors']:
 raise ValueError('Historical coverage incomplete: do not execute the three-season benchmark')
if len(fixtures)!=13:raise ValueError('Expected exactly 13 pregame fixtures excluding Knicks')
provisional={'predictions':fixtures,'created_at_utc':now(),'content_sha256':'collecting_before_final_snapshot'}
def capture(label,func):
 try:return label,func(provisional),None
 except Exception as e:return label,None,{'error':type(e).__name__,'detail':str(e),'observed_at_utc':now()}
data={};failures={}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for name,result,err in pool.map(lambda x:capture(*x),[('roster',rosters),('lineups',lineups),('official',retrieve),('sporting',sporting)]):
  if err:failures[name]=err
  else:data[name]=result
  print(name,'error' if err else 'captured',err or '',flush=True)
created=now();snapshot=generate(history,fixtures,created)
save('snapshot.json',snapshot)
for name in ('roster','sporting'):
 if name not in data:data[name]={'games':{}}
 data[name]['snapshot_sha256']=snapshot['content_sha256']
if 'lineups' in data:
 data['lineups'],candidates=data['lineups'];save('lineup_candidates.json',candidates)
else:data['lineups']={'games':{}}
data['lineups']['snapshot_sha256']=snapshot['content_sha256']
for name in ('roster','lineups','sporting'):save(name+'.json',data[name])
if 'official' in data:
 save('official_injury.json',data['official']);save('official_injury_rows.json',extract(data['official']['raw_page_text']))
save('source_failures.json',failures)
status=reconcile(snapshot,data['roster'],data['sporting']);save('status.json',status)
avail=resolve(snapshot,data['roster'],status,data['lineups']);save('availability.json',avail)
players={'players':[p for r in box['games'] for p in r['players']]}
rot=rotation(snapshot,history,players);save('rotation.json',rot)
mins=minutes(snapshot,rot,avail);save('minutes.json',mins)
branches=scenarios(snapshot,rot,avail);save('scenarios.json',branches)
report=build(snapshot,box,data['roster'],data['lineups'],avail,mins,branches)
save('report.json',report)
with (out/'report.md').open('x') as f:f.write(markdown(report))
manifest={'created_at_utc':now(),'files':{p.name:__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*')) if p.is_file()},'no_odds_input':True,'history_games':len(history),'boxscore_games':len(box['games'])}
save('manifest.json',manifest)
print('done',report['games_count'],sum(len(t['players']) for g in report['games'] for t in g['teams'].values()),flush=True)
