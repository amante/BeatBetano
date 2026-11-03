"""Join historical participation, projected identities and prior player history."""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def build(evidence,reference,history):
 if evidence.get('kind')!='nhl_pregame_player_evidence_v1' or reference.get('kind')!='nhl_prior_lineup_reference_v1' or history.get('kind')!='nhl_skater_history_capture_v1':raise ValueError('Wrong evidence kind')
 refs={str(g['game_id']):g for g in reference['games']}
 if len(refs)!=len(reference['games']):raise ValueError('Duplicate reference fixture')
 games=[]
 for game in evidence['games']:
  at=parse_utc(game['feature_as_of_utc']);start=parse_utc(game['start_utc'])
  if at>=start:raise ValueError('Not pregame')
  teams={}
  for team,side in game['teams'].items():
   prior=refs.get(str(game['game_id']),{}).get('teams',{}).get(team,{})
   if not side.get('projected_skaters_identity_complete') or not prior.get('players'):
    teams[team]=dict(status='blocked',reason='missing_complete_projected_lines_or_reference');continue
   source_at=parse_utc(prior['source']['retrieved_at'])
   if source_at>=start:raise ValueError('Late reference')
   old={p['player_id']:p for p in prior['players'] if p['role']!='goalie'}
   players=[p for role in ('forwards','defense') for line in side['projected'][role] for p in line]
   new={p['player_id']:p for p in players}
   if len(new)!=18 or len(players)!=18:raise ValueError('Incomplete or duplicate projected lineup')
   def observed(pid):
    rec=history['players'].get(str(pid))
    if rec is None:return None
    if rec['cutoff_exclusive']>history['cutoff_exclusive'] or rec['cutoff_exclusive']>=start.date().isoformat():raise ValueError('Invalid historical cutoff')
    if parse_utc(rec['source']['retrieved_at'])>=start:raise ValueError('Late player history')
    return rec
   def entry(pid):return dict(player_id=pid,name=(new.get(pid) or old[pid]).get('name'),history=observed(pid),previous_toi_seconds=old.get(pid,{}).get('observed_toi_seconds'))
   teams[team]=dict(status='projected_changes_observed_not_calibrated',out_of_projection=[entry(p) for p in sorted(old.keys()-new.keys())],new_in_projection=[entry(p) for p in sorted(new.keys()-old.keys())],projected_players=[entry(p) for p in sorted(new)],reported_injuries=side['projected'].get('injuries'),reported_scratches=side['projected'].get('scratches'),missing_history_ids=[p for p in sorted(old.keys()|new.keys()) if observed(p) is None],reference_source=prior['source'],editorial_source=game.get('editorial_source'),applied_to_probability=False)
  games.append(dict(game_id=game['game_id'],teams=teams))
 return dict(kind='nhl_projected_lineup_changes_v1',games=games,probabilities_modified=False,limitations=['Out of projection does not establish injury.','Historical TOI is not expected deployment.','Player effects remain unfitted; no probability delta is applied.'])

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ('evidence','reference','history','output'):p.add_argument('--'+key,required=True)
 a=p.parse_args();x=build(*(json.loads(Path(getattr(a,k)).read_text()) for k in ('evidence','reference','history')));Path(a.output).write_text(json.dumps(x,indent=2))
