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

def adjust(base,home,away):
 p=base['ml']['home']
 if type(p) not in (int,float) or not 0<p<1:raise ValueError('Invalid baseline')
 ratios=[]
 for side in (home,away):
  if side.get('status')!='conditional_replacement_scenario':raise ValueError('Incomplete exposure scenario')
  before=side['before']['goals'];after=side['after']['goals']
  if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (before,after)):raise ValueError('Missing positive goal rates')
  ratios.append(after/before)
 away_rate=away['before']['goals'];low=.000001;high=30.
 if not win_probability(low,away_rate)<=p<=win_probability(high,away_rate):raise ValueError('Baseline outside Poisson anchoring range')
 for _ in range(70):
  mid=(low+high)/2
  if win_probability(mid,away_rate)<p:low=mid
  else:high=mid
 home_rate=(low+high)/2;new=win_probability(home_rate*ratios[0],away_rate*ratios[1])
 return dict(baseline_ml_home=p,scenario_ml_home=new,scenario_ml_away=1-new,delta_home_pp=(new-p)*100,anchored_goals=dict(home=home_rate,away=away_rate),adjusted_goals=dict(home=home_rate*ratios[0],away=away_rate*ratios[1]),validated=False)

def build(publication,exposure,as_of):
 now=datetime.fromisoformat(as_of.replace('Z','+00:00'));rows=[]
 if now.tzinfo is None:raise ValueError('Timezone required')
 for game in publication['games']:
  if datetime.fromisoformat(game['start_utc'].replace('Z','+00:00'))<=now:continue
  matches=[r for r in exposure['games'] if str(r['game_id'])==str(game['game_id']) and all(r[k]==game[k] for k in ('home','away','start_utc'))]
  row={k:game[k] for k in ('game_id','home','away','start_utc')}
  try:
   if len(matches)!=1 or datetime.fromisoformat(exposure['as_of_utc'].replace('Z','+00:00'))>now:raise ValueError('Missing source identity or invalid time')
   teams=matches[0]['teams'];row.update(adjust(game,teams[game['home']],teams[game['away']]),status='experimental_minute_scenario')
  except (ValueError,KeyError,TypeError) as e:row.update(status='blocked',reason=str(e))
  rows.append(row)
 return dict(kind='nhl_minute_adjusted_ml_v1',as_of_utc=as_of,games=rows,validated=False,assumptions=['Historical goals/minute held constant under redistributed minutes.','Independent Poisson goals, with equal win chance on tied goals.','Home goal expectation anchored to original baseline ML; lineup goal ratios then applied.','No opponent, PP/PK, fatigue or line-chemistry effects; sensitivity scenario only.'])
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in ('publication','exposure','output'):p.add_argument('--'+k,required=True)
 a=p.parse_args();x=build(json.loads(Path(a.publication).read_text()),json.loads(Path(a.exposure).read_text()),datetime.now(timezone.utc).isoformat());Path(a.output).write_text(json.dumps(x,indent=2))
