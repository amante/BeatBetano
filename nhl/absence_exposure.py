"""Conditional replacement accounting using historical per-minute rates."""
METRICS={'goals':'skater_goals','assists':'skater_assists','shots':'skater_shots','penalty_minutes':'penalty_minutes'}
def rates(entry):
 h=entry.get('history')
 if not h or h.get('skater_games',0)<=0 or h.get('toi_seconds',0)<=0:return None
 return dict(player_id=entry['player_id'],name=entry.get('name'),minutes=h['toi_seconds']/60/h['skater_games'],per_minute={k:h[v]/(h['toi_seconds']/60) if h.get(v) is not None else None for k,v in METRICS.items()})
def contribution(row,minutes):return {k:v*minutes if v is not None else None for k,v in row['per_minute'].items()}
def totals(rows):
 return {k:sum(r[k] for r in rows) if all(r[k] is not None for r in rows) else None for k in METRICS}
def scenario(side):
 if side.get('status')!='projected_changes_observed_not_calibrated':return dict(status='blocked',reason=side.get('reason'))
 groups={k:[rates(e) for e in side[k]] for k in ('out_of_projection','new_in_projection','projected_players')}
 if any(r is None for rows in groups.values() for r in rows):return dict(status='blocked',reason='missing_individual_exposure')
 out,new,current=(groups[k] for k in ('out_of_projection','new_in_projection','projected_players'))
 incoming={r['player_id'] for r in new};retained=[r for r in current if r['player_id'] not in incoming]
 removed_minutes=sum(r['minutes'] for r in out);entry_minutes=sum(r['minutes'] for r in new)
 baseline_minutes=sum(r['minutes'] for r in retained)+removed_minutes
 if not current or baseline_minutes<=0:return dict(status='blocked',reason='no_reference_minutes')
 # Incoming players retain historical usage up to the available reference budget.
 factor=min(1,baseline_minutes/entry_minutes) if entry_minutes else 1
 entry_budget=entry_minutes*factor;remaining=baseline_minutes-entry_budget;retained_minutes=sum(r['minutes'] for r in retained)
 if remaining>0 and not retained_minutes:return dict(status='blocked',reason='no_retained_usage_for_allocation')
 allocated=[]
 for r in current:
  minutes=r['minutes']*factor if r['player_id'] in incoming else remaining*r['minutes']/retained_minutes if retained_minutes else 0
  allocated.append(dict(player_id=r['player_id'],name=r['name'],historical_minutes=r['minutes'],scenario_minutes=minutes,minutes_delta=minutes-r['minutes'],contribution=contribution(r,minutes)))
 lost=totals([contribution(r,r['minutes']) for r in out]);before=totals([contribution(r,r['minutes']) for r in retained+out]);after=totals([r['contribution'] for r in allocated])
 return dict(status='conditional_replacement_scenario',lost_minutes=removed_minutes,lost_historical_contribution=lost,incoming_historical_minutes=entry_minutes,incoming_historical_contribution=totals([contribution(r,r['minutes']) for r in new]),reference_minutes=baseline_minutes,allocated_minutes=sum(r['scenario_minutes'] for r in allocated),players=allocated,before=before,after=after,delta={k:after[k]-before[k] if before[k] is not None and after[k] is not None else None for k in METRICS},probability_delta=None,assumptions=['Incoming usage starts at its historical average; remaining budget is allocated proportionally to retained historical TOI.','Rates per minute are held constant; no line chemistry, opponent, special-team role or coach adjustment.','Reference budget is a sum of player historical averages, not verified regulation ice time.','Out of projection does not confirm injury.'])

def build(changes):
 return dict(kind='nhl_absence_exposure_v1',games=[dict(game_id=g['game_id'],teams={t:scenario(s) for t,s in g['teams'].items()}) for g in changes['games']],probabilities_modified=False)
if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('--changes',required=True);p.add_argument('--output',required=True);p.add_argument('--report');a=p.parse_args();result=build(json.loads(Path(a.changes).read_text()))
 if a.report:
  from datetime import datetime,timezone
  report=json.loads(Path(a.report).read_text());fixtures={str(g['game_id']):g for g in report['games']};result['as_of_utc']=datetime.now(timezone.utc).isoformat()
  for g in result['games']:
   f=fixtures[str(g['game_id'])];g.update({k:f[k] for k in ('home','away','start_utc')})
 Path(a.output).write_text(json.dumps(result,indent=2))
