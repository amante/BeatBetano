"""Research-only temporal lineup challenger; never installs a production model."""
import argparse,json,math
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def sigmoid(x):return 1/(1+math.exp(-max(-40,min(40,x))))
def metrics(predictions,labels):
 return dict(brier=sum((p-y)**2 for p,y in zip(predictions,labels))/len(labels),log_loss=-sum(y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p)) for p,y in zip(predictions,labels))/len(labels))
def evaluate(dataset,postmortems,train_end,test_end):
 if dataset.get('kind')!='nhl_lineup_labeled_dataset_v1':raise ValueError('Labeled dataset required')
 cut=parse_utc(train_end);end=parse_utc(test_end)
 if cut>=end:raise ValueError('Invalid temporal boundaries')
 baselines={}
 for report in postmortems:
  for score in report.get('market_scores',[]):
   if score['market']!='ml':continue
   p=score['probabilities'].get('home');gid=str(score['game_id'])
   if type(p) not in (int,float) or not 0<p<1:continue
   value=(p,parse_utc(score['prediction_as_of_utc']))
   if gid in baselines and baselines[gid]!=value:raise ValueError('Ambiguous baseline emission')
   baselines[gid]=value
 train=[];test=[];seen=set();excluded=[]
 for row in dataset['rows']:
  gid=str(row['game_id']);start=parse_utc(row['start_utc'])
  if gid in seen:raise ValueError('Duplicate game')
  seen.add(gid)
  if parse_utc(row['feature_as_of_utc'])>=start:raise ValueError('Poststart feature')
  baseline=baselines.get(gid)
  if baseline is None:excluded.append(dict(game_id=gid,reason='missing_baseline'));continue
  if baseline[1]>=start:raise ValueError('Poststart baseline')
  values=[]
  for team in (row['home'],row['away']):
   groups=row['features'][team]['groups'];rates=[]
   for key in ('new_in_projection','out_of_projection'):
    group=groups[key]
    if not group['complete']:raise ValueError('Incomplete lineup features')
    rates.append(sum(p['toi_minutes_per_game'] for p in group['per_player']))
   values.append(rates[0]-rates[1])
  x=(values[0]-values[1])/60;y=row['target_ml_home']
  if y not in (0,1) or not math.isfinite(x):raise ValueError('Invalid feature or label')
  item=(gid,math.log(baseline[0]/(1-baseline[0])),x,y,baseline[0])
  if start<=cut:train.append(item)
  elif start<=end:test.append(item)
 result=dict(kind='nhl_lineup_candidate_evaluation_v1',train_end=train_end,test_end=test_end,train_games=len(train),test_games=len(test),excluded=excluded,feature='home_minus_away_difference_in_historical_TOI_of_entries_minus_exits_hours',production_approved=False,parameters=None,metrics=None)
 if len(train)<20 or len(test)<20 or len({r[3] for r in train})<2 or len({r[3] for r in test})<2:
  return dict(result,status='blocked_insufficient_temporal_samples',limitations=['20 per partition is an execution floor, not evidence of adequate statistical power.'])
 # Fixed regularized offset logistic model; baseline offset stays unchanged.
 intercept=weight=0.
 for _ in range(2000):
  residual=[sigmoid(r[1]+intercept+weight*r[2])-r[3] for r in train]
  intercept-=.05*(sum(residual)/len(train)+.01*intercept)
  weight-=.05*(sum(e*r[2] for e,r in zip(residual,train))/len(train)+.01*weight)
 labels=[r[3] for r in test];base=metrics([r[4] for r in test],labels);candidate=metrics([sigmoid(r[1]+intercept+weight*r[2]) for r in test],labels)
 return dict(result,status='research_evaluated_not_approved',parameters=dict(intercept=intercept,weight=weight),metrics=dict(baseline=base,candidate=candidate),test_game_ids=[r[0] for r in test],limitations=['Single temporal comparison does not authorize deployment.','Historical TOI is an observed exposure proxy, not expected performance or injury causality.'])
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ('dataset','train-end','test-end','output'):p.add_argument('--'+key,required=True)
 p.add_argument('--postmortems',default='frontend/data/nhl-postmortems');a=p.parse_args()
 result=evaluate(json.loads(Path(a.dataset).read_text()),[json.loads(f.read_text()) for f in Path(a.postmortems).glob('*.json')],a.train_end,a.test_end);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
