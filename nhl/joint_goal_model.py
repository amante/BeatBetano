"""One fitted goal process for skater/goalie/special-team inputs; no default weights."""
import math
from nhl.pulso_pregame_v7 import parse_utc
from nhl.minute_adjusted_ml import win_probability
FEATURES=('skater_goals_per60','skater_assists_per60','skater_shots_per60','skater_pim_per60','opponent_defensive_shots_allowed_per60','opponent_goalie_save_pct','powerplay_goals_per_opportunity','opponent_penaltykill_goals_per_opportunity','expected_powerplay_opportunities','line_continuity')

def vector(side):
 values=[]
 for key in FEATURES:
  v=side.get(key)
  if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Missing or invalid '+key)
  if v<0:raise ValueError('Negative sporting input')
  if key in ('opponent_goalie_save_pct','powerplay_goals_per_opportunity','opponent_penaltykill_goals_per_opportunity','line_continuity') and v>1:raise ValueError('Rate out of range')
  values.append(v)
 return values

def fit(rows,epochs=1500,rate=.01,l2=.01):
 """Rows must already be frozen pregame, with separate regulation-goal targets."""
 if not rows:raise ValueError('No real training observations')
 xs=[vector(r['features']) for r in rows];ys=[r['regulation_goals'] for r in rows]
 if any(type(y) is not int or y<0 for y in ys):raise ValueError('Invalid regulation target')
 seen=set()
 for row in rows:
  key=(str(row['game_id']),row['team'])
  if key in seen:raise ValueError('Duplicate game/team training observation')
  seen.add(key)
  if parse_utc(row['feature_as_of_utc'])>=parse_utc(row['start_utc']):raise ValueError('Poststart training input')
 n=len(rows);means=[sum(x[j] for x in xs)/n for j in range(len(FEATURES))]
 scales=[math.sqrt(sum((x[j]-means[j])**2 for x in xs)/n) for j in range(len(FEATURES))]
 if any(s<1e-8 for s in scales):raise ValueError('Unidentifiable constant sporting feature')
 z=[[(x[j]-means[j])/scales[j] for j in range(len(FEATURES))] for x in xs]
 bias=math.log(max(sum(ys)/n,.01));weights=[0.]*len(FEATURES)
 for _ in range(epochs):
  errors=[math.exp(max(-12,min(5,bias+sum(w*v for w,v in zip(weights,x)))))-y for x,y in zip(z,ys)]
  bias-=rate*sum(errors)/n
  weights=[w-rate*(sum(e*x[j] for e,x in zip(errors,z))/n+l2*w) for j,w in enumerate(weights)]
 return dict(kind='nhl_joint_goal_model_v1',features=list(FEATURES),means=means,scales=scales,weights=weights,bias=bias,training_observations=n,validated=False)

def expected_goals(side,model):
 if model.get('kind')!='nhl_joint_goal_model_v1' or model.get('features')!=list(FEATURES):raise ValueError('Incompatible fitted goal model')
 x=vector(side);arrays=[model[k] for k in ('means','scales','weights')]
 if any(len(a)!=len(FEATURES) for a in arrays) or any(type(v) not in (int,float) or not math.isfinite(v) for a in arrays for v in a) or any(s<=0 for s in model['scales']):raise ValueError('Invalid fitted parameters')
 z=model['bias']+sum(w*(v-m)/s for v,m,s,w in zip(x,*arrays))
 if not math.isfinite(z) or not -12<=z<=math.log(30):raise ValueError('Goal expectation outside supported domain')
 return math.exp(z)

def predict(home,away,model):
 h=expected_goals(home,model);a=expected_goals(away,model)
 def dist(rate):
  v=[math.exp(-rate)]
  for i in range(1,150):v.append(v[-1]*rate/i)
  return v
 hd,ad=dist(h),dist(a);draw=sum(x*y for x,y in zip(hd,ad));ml=win_probability(h,a)
 return dict(expected_regulation_goals=dict(home=h,away=a),ml=dict(home=ml,away=1-ml),rt=dict(home=ml-.5*draw,draw=draw,away=1-ml-.5*draw),component_features=list(FEATURES),validated=False,assumptions=['Independent regulation-goal Poisson processes; equal overtime/shootout win probability on ties.','Feature effects must be estimated from prior-game inputs; no default coefficients.','Assists, shots and goals are correlated predictors, not additive goal events.','Penalities are not automatically converted to powerplays.'])
