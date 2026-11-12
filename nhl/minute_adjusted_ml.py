"""Explicit Poisson sensitivity scenario, baseline anchored; research only."""
import argparse,json,math
from datetime import datetime,timezone
from pathlib import Path

def win_probability(home,away):
 if not all(math.isfinite(x) and 0<x<=30 for x in (home,away)):raise ValueError('Invalid goal expectation')
 def probs(rate):
  values=[math.exp(-rate)]
  for n in range(1,150):values.append(values[-1]*rate/n)
  return values
 h,a=probs(home),probs(away);cumulative=0.;p=0.
 for n,hp in enumerate(h):
  p+=hp*(cumulative+.5*a[n]);cumulative+=a[n]
 return p

def solve_home_rate(probability,away_rate):
 low,high=.000001,30.
 if not win_probability(low,away_rate)<=probability<=win_probability(high,away_rate):raise ValueError('Baseline outside Poisson anchoring range')
 for _ in range(70):
  mid=(low+high)/2
  if win_probability(mid,away_rate)<probability:low=mid
  else:high=mid
 return (low+high)/2

def solve_away_rate(probability,home_rate):
 low,high=.000001,30.
 if not win_probability(home_rate,high)<=probability<=win_probability(home_rate,low):raise ValueError('Baseline outside Poisson anchoring range')
 for _ in range(70):
  mid=(low+high)/2
  if win_probability(home_rate,mid)>probability:low=mid
  else:high=mid
 return (low+high)/2

def side_metrics(side):
 if not isinstance(side,dict) or side.get('status')!='conditional_replacement_scenario':return None
 before_data=side.get('before') or {};after_data=side.get('after') or {};before=before_data.get('goals');after=after_data.get('goals')
 if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (before,after)):return None
 return {'before':before,'ratio':after/before}

def adjust(base,home,away,home_code='home',away_code='away'):
 p=base['ml']['home']
 if type(p) not in (int,float) or not 0<p<1:raise ValueError('Invalid baseline')
 home_metrics,away_metrics=side_metrics(home),side_metrics(away)
 if home_metrics is None and away_metrics is None:raise ValueError('No complete team exposure scenario')
 if away_metrics is not None:
  away_rate=away_metrics['before']
  home_rate=solve_home_rate(p,away_rate)
 else:
  home_rate=home_metrics['before']
  away_rate=solve_away_rate(p,home_rate)
 home_ratio=home_metrics['ratio'] if home_metrics else 1.
 away_ratio=away_metrics['ratio'] if away_metrics else 1.
 adjusted_home,adjusted_away=home_rate*home_ratio,away_rate*away_ratio
 new=win_probability(adjusted_home,adjusted_away)
 adjusted_sides=[code for code,metrics in ((home_code,home_metrics),(away_code,away_metrics)) if metrics is not None]
 excluded_sides=[code for code,metrics in ((home_code,home_metrics),(away_code,away_metrics)) if metrics is None]
 return dict(baseline_ml_home=p,scenario_ml_home=new,scenario_ml_away=1-new,delta_home_pp=(new-p)*100,
  anchored_goals=dict(home=home_rate,away=away_rate),adjusted_goals=dict(home=adjusted_home,away=adjusted_away),
  adjusted_sides=adjusted_sides,excluded_sides=excluded_sides,partial=bool(excluded_sides),validated=False)

def build(publication,exposure,as_of):
 now=datetime.fromisoformat(as_of.replace('Z','+00:00'));rows=[]
 if now.tzinfo is None:raise ValueError('Timezone required')
 for game in publication['games']:
  if datetime.fromisoformat(game['start_utc'].replace('Z','+00:00'))<=now:continue
  matches=[r for r in exposure['games'] if str(r['game_id'])==str(game['game_id']) and all(r[k]==game[k] for k in ('home','away','start_utc'))]
  row={k:game[k] for k in ('game_id','home','away','start_utc')}
  try:
   if len(matches)!=1 or datetime.fromisoformat(exposure['as_of_utc'].replace('Z','+00:00'))>now:raise ValueError('Missing source identity or invalid time')
   teams=matches[0]['teams']
   row.update(adjust(game,teams[game['home']],teams[game['away']],game['home'],game['away']),status='experimental_minute_scenario')
  except (ValueError,KeyError,TypeError) as e:row.update(status='blocked',reason=str(e))
  rows.append(row)
 return dict(kind='nhl_minute_adjusted_ml_v1',as_of_utc=as_of,games=rows,validated=False,assumptions=[
  'Historical goals/minute held constant under redistributed minutes.',
  'Independent Poisson goals, with equal win chance on tied goals.',
  'Home goal expectation anchored to original baseline ML; lineup goal ratios then applied.',
  'When one team exposure is incomplete, its rate is held at the baseline-anchored value; only the complete team rate is adjusted.',
  'No opponent, PP/PK, fatigue or line-chemistry effects; sensitivity scenario only.'])
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in ('publication','exposure','output'):p.add_argument('--'+k,required=True)
 a=p.parse_args();x=build(json.loads(Path(a.publication).read_text()),json.loads(Path(a.exposure).read_text()),datetime.now(timezone.utc).isoformat());Path(a.output).write_text(json.dumps(x,indent=2))
