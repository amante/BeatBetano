"""Descriptive lineup features with complete-case coverage; no invented weights."""
import argparse,json
from pathlib import Path

def aggregate(entries):
    totals=dict(games=0,goals=0,shots=0,toi_seconds=0)
    missing=[];per_player=[]
    for entry in entries:
        pid=entry['player_id'];h=entry.get('history')
        if not h or h.get('skater_games',0)<=0 or h.get('toi_games')!=h.get('skater_games'):
            missing.append(pid);continue
        for source,target in [('skater_games','games'),('skater_goals','goals'),('skater_shots','shots'),('toi_seconds','toi_seconds')]:
            value=h.get(source)
            if type(value) is not int or value<0:raise ValueError('Invalid individual counts')
            totals[target]+=value
        per_player.append(dict(player_id=pid,goals_per_game=h['skater_goals']/h['skater_games'],shots_per_game=h['skater_shots']/h['skater_games'],toi_minutes_per_game=h['toi_seconds']/h['toi_games']/60))
    return dict(players=len(entries),observed_players=len(per_player),missing_player_ids=missing,complete=not missing,observed_totals=totals,per_player=per_player,mean_historical_toi_minutes=sum(p['toi_minutes_per_game'] for p in per_player)/len(per_player) if per_player and not missing else None)

def build(changes):
    if changes.get('kind')!='nhl_projected_lineup_changes_v1':raise ValueError('Lineup changes required')
    games=[]
    for game in changes['games']:
        teams={}
        for team,side in game['teams'].items():
            if side.get('status')!='projected_changes_observed_not_calibrated':
                teams[team]=dict(status='blocked',reason=side.get('reason'));continue
            groups={key:aggregate(side[key]) for key in ('out_of_projection','new_in_projection','projected_players')}
            groups['projected_forwards']=aggregate([p for p in side['projected_players'] if p.get('position_group')=='forwards'])
            groups['projected_defense']=aggregate([p for p in side['projected_players'] if p.get('position_group')=='defense'])
            teams[team]=dict(status='descriptive_features_only',groups=groups,applied_to_probability=False)
        games.append(dict(game_id=game['game_id'],teams=teams))
    return dict(kind='nhl_lineup_feature_packet_v1',games=games,probabilities_modified=False,limitations=['Counts are observed historical exposures, not expected performance.','Unequal player sample sizes are retained, not treated as equal exposures.','No injury causality, prospective minutes or fitted probability contribution is asserted.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--changes',required=True);p.add_argument('--output',required=True);a=p.parse_args();Path(a.output).write_text(json.dumps(build(json.loads(Path(a.changes).read_text())),indent=2))
