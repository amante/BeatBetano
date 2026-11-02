import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from nhl.daily_postmortem import analyze,save,run,read
from nhl.pulso_collective_audit_208 import freeze_prediction

DAY='2026-11-01';NOW=datetime(2026,11,2,12,tzinfo=timezone.utc)
def payload(state='OFF',scores=(3,0)):
 home,away=scores;plays=[];h=a=0
 for i,side in enumerate(['home']*home+['away']*away):
  h+=side=='home';a+=side=='away'
  plays.append({'eventId':i+1,'typeDescKey':'goal','timeInPeriod':'%02d:00'%(i+1),'periodDescriptor':{'number':1,'periodType':'REG'},'details':{'eventOwnerTeamId':1 if side=='home' else 2,'homeScore':h,'awayScore':a}})
 return {'id':2026020227,'gameState':state,'startTimeUTC':'2026-11-01T18:00:00Z','homeTeam':{'id':1,'abbrev':'CAR','score':home},'awayTeam':{'id':2,'abbrev':'WPG','score':away},'plays':plays}
class DailyPostmortem(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.repo=Path(self.tmp.name)
  self.pbp=payload();self.final=copy.deepcopy(self.pbp);self.final.pop('plays')
  self.add_forecast('1','2026-11-01T12:00:00Z',.6);self.add_forecast('2','2026-11-01T13:00:00Z',.9)
 def add_forecast(self,run,stamp,p):
  r={'game_id':'2026020227','home':'CAR','away':'WPG','start_utc':'2026-11-01T18:00:00Z','prediction_as_of_utc':stamp,'source_asof_utc':stamp,'source_url':'https://www.nhl.com','model_version':'test-1','market':'ml','probabilities':{'home':p,'away':1-p},'odds_used_in_model':False,'point_in_time_sources_verified':True,'official':False}
  path=self.repo/'frontend/data/nhl-forecasts'/('run-'+run)/'2026020227-ml.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(freeze_prediction(r)))
 def get(self,url):return copy.deepcopy(self.pbp if 'play-by-play' in url else {'games':[self.final]})
 def test_original_issuance_and_idempotent_archival(self):
  core,sources,forecasts=analyze(self.repo,DAY,self.get,NOW)
  self.assertEqual(core['status'],'complete');self.assertEqual(core['source_forecast_files'],2);self.assertEqual(core['unique_forecast_issuances'],1)
  self.assertAlmostEqual(core['metrics'][0]['brier'],.16);self.assertEqual(core['metrics'][0]['modal_correct'],1)
  first=run(self.repo,[DAY],self.get,NOW);before={str(p):p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
  self.assertEqual(run(self.repo,[DAY],self.get,NOW),first);self.assertEqual(before,{str(p):p.read_bytes() for p in self.repo.rglob('*') if p.is_file()})
  learning=read(self.repo/'nhl/learning/postmortems'/ (DAY+'.json'));self.assertFalse(learning['applied_to_live_parameters']);self.assertEqual(len(learning['observations']),1)
 def test_pending_game_not_scored_and_retry_finishes(self):
  self.final['gameState']=self.pbp['gameState']='LIVE';run(self.repo,[DAY],self.get,NOW)
  pending=read(self.repo/'frontend/data/nhl-postmortems'/(DAY+'.json'));self.assertEqual(pending['status'],'pending_results');self.assertEqual(pending['metrics'],[])
  self.final['gameState']=self.pbp['gameState']='OFF';run(self.repo,[DAY],self.get,NOW)
  complete=read(self.repo/'frontend/data/nhl-postmortems'/(DAY+'.json'));self.assertEqual(complete['graded_games'],1);self.assertEqual(len(list((self.repo/'reports/nhl/daily'/DAY/'revisions').iterdir())),2)
 def test_bad_goal_sequence_and_cross_source_mismatch_not_scored(self):
  self.pbp['plays'][0]['details']['homeScore']=3
  core,_,_=analyze(self.repo,DAY,self.get,NOW);self.assertEqual(core['status'],'needs_review');self.assertEqual(core['graded_games'],0)
  self.pbp=payload();self.final['homeTeam']['score']=4
  core,_,_=analyze(self.repo,DAY,self.get,NOW);self.assertTrue(core['source_errors']);self.assertEqual(core['metrics'],[])
 def test_source_outage_never_erases_existing_complete_report(self):
  run(self.repo,[DAY],self.get,NOW);path=self.repo/'frontend/data/nhl-postmortems'/(DAY+'.json');before=path.read_bytes()
  def fail(url):raise OSError('unavailable')
  result=run(self.repo,[DAY],fail,NOW);self.assertEqual(result[0]['status'],'preserved_previous_result');self.assertTrue(result[0]['source_errors']);self.assertEqual(path.read_bytes(),before)
 def test_official_correction_keeps_old_revision(self):
  run(self.repo,[DAY],self.get,NOW);self.pbp=payload(scores=(0,3));self.final=copy.deepcopy(self.pbp);self.final.pop('plays');run(self.repo,[DAY],self.get,NOW)
  path=self.repo/'reports/nhl/daily'/DAY/'revisions';self.assertEqual(len(list(path.iterdir())),2)
  report=read(self.repo/'frontend/data/nhl-postmortems'/(DAY+'.json'));self.assertEqual(report['metrics'][0]['modal_correct'],0)
 def test_tampered_and_poststart_forecasts_rejected(self):
  path=next((self.repo/'frontend/data/nhl-forecasts/run-1').glob('*.json'));x=read(path);x['record']['probabilities']={'home':.7,'away':.3};path.write_text(json.dumps(x))
  with self.assertRaises(ValueError):analyze(self.repo,DAY,self.get,NOW)
  x['record']['prediction_as_of_utc']=x['record']['start_utc'];path.write_text(json.dumps(x))
  with self.assertRaisesRegex(ValueError,'postgame|Out-of-order'):analyze(self.repo,DAY,self.get,NOW)
 def test_future_day_rejected(self):
  with self.assertRaises(ValueError):analyze(self.repo,'2026-11-03',self.get,NOW)
 def test_no_forecasts_do_not_create_fake_observations(self):
  for file in (self.repo/'frontend/data/nhl-forecasts').glob('*/*.json'):file.unlink()
  run(self.repo,[DAY],self.get,NOW);report=read(self.repo/'frontend/data/nhl-postmortems'/(DAY+'.json'))
  self.assertEqual(report['status'],'no_forecasts');self.assertEqual(report['graded_games'],0);self.assertEqual(report['metrics'],[])
if __name__=='__main__':unittest.main()
