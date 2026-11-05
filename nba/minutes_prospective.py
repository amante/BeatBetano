"""Frozen conditional-minute research projections, separate from ML forecasts."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from minutes_research import appearances,features,predict
from sporting_archive import actual_games,bundles,team_observation
from forward_capture import DEFAULT_PROTOCOL
from forward_ledger import reconstruct,load_observations,save_new
from reproducible_slate import digest
from prospective import utc


def forecast(archive,model,protocol,fixtures,records,as_of):
    now=utc(as_of);history={}
    # A live research forecast uses real collection timestamps, unlike the
    # explicitly retrospective historical reconstruction used for backtesting.
    allowed={'games':[g for g in archive['games'] if utc(g['observed_at_utc'])<=now and utc(g['game']['tipoff_utc'])<now]}
    for g in appearances(allowed):
        for key,p in g['players'].items():
            if p['did_not_play'] or p['minutes_played'] is None:continue
            history.setdefault(key,[]).append({'game_id':str(g['fixture']['game_id']),'tip':g['tip'],'minutes':p['minutes_played']})
    rows=[]
    for fixture in fixtures:
        if utc(fixture['tipoff_utc'])<=now:continue
        teams={}
        for team in (fixture['home_team'],fixture['away_team']):
            source=team_observation(records,fixture['game_id'],team,fixture['tipoff_utc'],as_of)
            players=[]
            for p in source['players'] if source else []:
                f=features(history.get((team,p['player_id']),[]),utc(fixture['tipoff_utc']),protocol)
                players.append({'player_id':p['player_id'],'player':p['player'],
                    'reported_status':p['status'],'conditional_last_five_minutes':f['baseline'] if f else None,
                    'conditional_candidate_minutes':predict(model,f['x']) if f else None,
                    'prior_game_ids':f['prior_game_ids'] if f else [],
                    'expected_game_minutes':None,'participation_probability':None,
                    'status':'experimental_if_appears' if f else 'PASS_insufficient_history'})
            teams[team]={'players':players,'roster_observed_at_utc':source['observed_at_utc'] if source else None,
                         'regulation_allocations':None,'total_240_minutes_claimed':False}
        rows.append({**fixture,'teams':teams,'status':'conditional_component_only_full_rotation_PASS'})
    return {'kind':'nba_conditional_minutes_research_v1','created_at_utc':as_of,'games':rows,
            'training_model_sha256':digest(model),'research_protocol_sha256':digest(protocol),
            'context_archive_sha256':digest(allowed),'production_approved':False,
            'ml_modified':False,'no_odds_input':True,
            'interpretation':'Minutes IF the player appears, not probability of playing, expected unconditional minutes, or a full rotation. Status observations do not change either model.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evaluation',required=True);p.add_argument('--research-protocol',required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    research=json.loads(Path(a.research_protocol).read_text());evaluation=json.loads(Path(a.evaluation).read_text())
    if evaluation['protocol_sha256']!=digest(research) or digest(evaluation['model'])!=evaluation['model_sha256']:
        raise ValueError('Research model/protocol mismatch')
    base=json.loads(Path('reports/nba-2026-11-04/boxscores.json').read_text())
    known={str(g['game']['game_id']) for g in base['games']}
    for current in actual_games('reports/nba-sporting'):
        if current['game']['game_id'] not in known:base['games'].append(current)
    asof=datetime.now(timezone.utc).isoformat()
    cohort=json.loads(Path(DEFAULT_PROTOCOL).read_text())
    ledger=reconstruct(load_observations('reports/nba-forward'),cohort,asof)
    fixtures=[{k:g[k] for k in ('game_id','home_team','away_team','tipoff_utc')} for g in ledger['games'] if g['source_state']=='pre' and utc(g['tipoff_utc'])>utc(asof)]
    sources,errors=bundles('reports/nba-sporting')
    result=forecast(base,evaluation['model'],research,fixtures,sources,asof)
    result['source_errors']=errors
    result['content_sha256']=digest(result)
    save_new(a.output,result)
    print(json.dumps({'future_games':len(result['games']),'roster_players':sum(len(t['players']) for g in result['games'] for t in g['teams'].values()),
                      'conditional_estimates':sum(p['conditional_candidate_minutes'] is not None for g in result['games'] for t in g['teams'].values() for p in t['players'])}))

if __name__=='__main__':main()
