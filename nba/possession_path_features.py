"""Derive turnover pressure and scoring-run blocks from verified possessions.

Input is an authorized normalized possession export, not raw play-by-play shots:
rebounds/free throws must already have been reconciled into possessions.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from postmortem_engine import no_market_fields, provenance
from prospective import utc
from reproducible_slate import digest


def extract(archive, created_at, target_tipoff):
    created, tip = utc(created_at), utc(target_tipoff)
    if created >= tip:
        raise ValueError('Feature extraction must be pregame')
    no_market_fields(archive)
    teams = defaultdict(lambda:{'possessions':0,'turnovers':0,'opponent_possessions':0,
                                'forced_turnovers':0,'minutes':0,'game_ids':[],
                                'non_turnover_blocks':[],'after_turnover':[],'other':[],
                                'max_leads':[]})
    seen = set()
    for game in sorted(archive['games'],key=lambda g:(utc(g['tipoff_utc']),str(g['game_id']))):
        gid = str(game['game_id'])
        if gid in seen:
            raise ValueError('Duplicate path game')
        seen.add(gid)
        start = utc(game['tipoff_utc'])
        end = utc(game['completed_at_utc'])
        if not start < end <= created:
            raise ValueError('Incomplete or future historical path')
        provenance(game['evidence'],created,tip,'historical score path')
        if utc(game['evidence']['available_at_utc']) < end:
            raise ValueError('Completed path published before completion')
        if game.get('complete') is not True:
            raise ValueError('Partial possession path')
        home,away = game['home_team'],game['away_team']
        if home == away:
            raise ValueError('Invalid path teams')
        duration = game['duration_minutes']
        if type(duration) is not int or duration < 48 or (duration-48)%5:
            raise ValueError('Invalid regulation/overtime duration')
        points = {home:0,away:0}
        leads = {home:0,away:0}
        buffers = {home:[],away:[]}
        previous = None
        for sequence, event in enumerate(game['possessions']):
            if event['sequence'] != sequence:
                raise ValueError('Noncontiguous possession sequence')
            t = event['team']
            if t not in points:
                raise ValueError('Possession team mismatch')
            opponent = away if t == home else home
            scored = event['points']
            turnover = event['turnover']
            if type(scored) is not int or not 0 <= scored <= 4 or type(turnover) is not bool:
                raise ValueError('Invalid possession outcome')
            if turnover and scored:
                raise ValueError('Turnover possession scored points')
            points[t] += scored
            leads[t] = max(leads[t],points[t]-points[opponent])
            teams[t]['possessions'] += 1
            teams[t]['turnovers'] += int(turnover)
            teams[opponent]['opponent_possessions'] += 1
            teams[opponent]['forced_turnovers'] += int(turnover)
            if not turnover:
                after = previous is not None and previous['team'] == opponent and previous['turnover']
                teams[t]['after_turnover' if after else 'other'].append(scored)
                buffers[t].append(scored)
                if len(buffers[t]) == 4:
                    teams[t]['non_turnover_blocks'].append(buffers[t])
                    buffers[t] = []
            previous = event
        if points != {home:game['home_points'],away:game['away_points']} or points[home] == points[away]:
            raise ValueError('Score path does not reconcile with final score')
        for t in (home,away):
            teams[t]['minutes'] += duration
            teams[t]['game_ids'].append(gid)
            teams[t]['max_leads'].append(leads[t])
    output = {}
    for t, values in teams.items():
        after,other = values['after_turnover'],values['other']
        blocks = values['non_turnover_blocks']
        if min(len(after),len(other)) < 10 or len(blocks) < 3 or len(values['game_ids']) < 3:
            output[t] = {'status':'PASS_insufficient_path_sample','game_ids':values['game_ids']}
            continue
        bonus = max(0,sum(after)/len(after)-sum(other)/len(other))
        if bonus > 1:
            output[t] = {'status':'PASS_transition_bonus_outside_supported_range','game_ids':values['game_ids']}
            continue
        output[t] = {'status':'research_features_only','path_sample_possessions':values['possessions'],
                     'pace_regulation':48*values['possessions']/values['minutes'],
                     'turnover_rate':values['turnovers']/values['possessions'],
                     'forced_turnover_rate':values['forced_turnovers']/values['opponent_possessions'],
                     'transition_bonus':bonus,'non_turnover_blocks':blocks,
                     'offensive_explosiveness':{'blocks':len(blocks),
                                               'eight_plus_points_in_four_non_turnover_possessions':sum(sum(b)>=8 for b in blocks)/len(blocks)},
                     'game_ids':values['game_ids'],'historical_max_leads':values['max_leads']}
    return {'created_at_utc':created_at,'target_tipoff_utc':target_tipoff,'teams':output,
            'input_sha256':digest(archive),'calibrated':False,
            'limitations':['Blocks preserve four consecutive non-turnover scoring opportunities; turnovers are modeled separately.',
                           'Four-point maximum excludes unusual technical/free-throw possessions; reconcile upstream or PASS.',
                           'Transition bonus is descriptive, not a causal fast-break estimate.']}


def main():
    p = argparse.ArgumentParser()
    for field in ('archive','created-at','tipoff','output'):
        p.add_argument('--'+field,required=True)
    a = p.parse_args()
    result = extract(json.loads(Path(a.archive).read_text()),a.created_at,a.tipoff)
    with Path(a.output).open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False)


if __name__ == '__main__':
    main()
