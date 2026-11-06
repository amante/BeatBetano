"""Experimental offensive/defensive ridge coefficients from verified lineup possessions.

Coefficients adjust jointly for observed teammates/opponents and home offense.
They are associations, not causal injury effects or independently validated RAPM.
"""
import math
from collections import Counter, defaultdict
from possession_path_features import extract
from postmortem_engine import no_market_fields, provenance
from prospective import utc
from reproducible_slate import digest
from score_path import number

VERSION = 'regularized_possession_effect_v1'
PARAMETERS = {'ridge_penalty':1000., 'minimum_side_possessions':100,
              'minimum_games':3, 'tolerance':1e-9, 'maximum_iterations':500}


def ridge(design, outcomes, width, penalty):
    """Conjugate gradients on sparse ridge normal equations; intercept unpenalized."""
    number(penalty, 1e-6, 1e9, 'ridge penalty')
    if not design or len(design) != len(outcomes):
        raise ValueError('Empty or unmatched regression design')
    rhs = [0.]*width
    for row,y in zip(design,outcomes):
        number(y,0,400,'possession points per 100')
        for j in row:rhs[j] += y
    def product(v):
        out = [0.]+[penalty*x for x in v[1:]]
        for row in design:
            value = sum(v[j] for j in row)
            for j in row:out[j] += value
        return out
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    beta=[0.]*width
    residual=rhs[:]
    direction=residual[:]
    norm=dot(residual,residual)
    target=PARAMETERS['tolerance']**2 * max(1.,norm)
    for iteration in range(PARAMETERS['maximum_iterations']):
        if norm <= target:return beta,iteration
        projected=product(direction)
        denominator=dot(direction,projected)
        if denominator <= 0 or not math.isfinite(denominator):
            raise ValueError('Unstable player-effect system')
        step=norm/denominator
        beta=[x+step*d for x,d in zip(beta,direction)]
        residual=[r-step*a for r,a in zip(residual,projected)]
        updated=dot(residual,residual)
        direction=[r+updated/norm*d for r,d in zip(residual,direction)]
        norm=updated
    raise ValueError('Player-effect solver did not converge')


def fit(archive, created_at, tipoff):
    # Shared validation reconciles scores, timestamps, IDs, turnover outcomes and units.
    extract(archive,created_at,tipoff)
    no_market_fields(archive)
    players=set()
    membership={}
    events=[]
    exposure=defaultdict(Counter)
    games_seen=defaultdict(set)
    through=None
    for game in archive['games']:
        end=utc(game['completed_at_utc'])
        if end >= utc(created_at):raise ValueError('Player metrics window reaches cutoff')
        through=max(through,end) if through else end
        provenance(game['lineup_evidence'],utc(created_at),utc(tipoff),'historical possession lineups')
        if game.get('lineup_attribution') != 'possession_start':
            raise ValueError('Explicit possession-start lineup attribution required')
        teams=(game['home_team'],game['away_team'])
        rosters=game['team_rosters']
        if set(rosters) != set(teams):raise ValueError('Missing historical roster identities')
        for team,ids in rosters.items():
            if len(ids)<5 or len(set(ids))!=len(ids) or any(not isinstance(p,str) or not p for p in ids):
                raise ValueError('Invalid historical roster')
        if set(rosters[teams[0]]) & set(rosters[teams[1]]):
            raise ValueError('Player on both historical rosters')
        for event in game['possessions']:
            offense=event['team']; defense=teams[1] if offense==teams[0] else teams[0]
            on,against=event['offense_lineup'],event['defense_lineup']
            if any(len(lineup)!=5 or len(set(lineup))!=5 for lineup in (on,against)):
                raise ValueError('Need five unique players on each side of every possession')
            if not set(on)<=set(rosters[offense]) or not set(against)<=set(rosters[defense]):
                raise ValueError('Lineup player outside historical team roster')
            for team,lineup,side in ((offense,on,'offense'),(defense,against,'defense')):
                for pid in rosters[team]:
                    exposure[pid][side+'_team_total']+=1
                for pid in lineup:
                    players.add(pid)
                    exposure[pid][side]+=1
                    games_seen[pid].add(str(game['game_id']))
                    membership.setdefault(pid,set()).add(team)
            events.append((on,against,offense==teams[0],100*event['points']))
    if not events:raise ValueError('No historical lineup possessions')
    ids=sorted(players)
    columns={(side,pid):2+i+offset*len(ids) for offset,side in enumerate(('offense','defense')) for i,pid in enumerate(ids)}
    design=[(0,)+( (1,) if home else () )+tuple(columns['offense',p] for p in on)+tuple(columns['defense',p] for p in against)
            for on,against,home,y in events]
    beta,iterations=ridge(design,[y for on,against,home,y in events],2+2*len(ids),PARAMETERS['ridge_penalty'])
    output={}
    for pid in ids:
        counts=exposure[pid]
        sufficient=(min(counts['offense'],counts['defense'])>=PARAMETERS['minimum_side_possessions']
                    and len(games_seen[pid])>=PARAMETERS['minimum_games']
                    and all(counts[s+'_team_total']>counts[s] for s in ('offense','defense')))
        off,defense=beta[columns['offense',pid]],beta[columns['defense',pid]]
        supported=all(math.isfinite(v) and abs(v)<=30 for v in (off,defense))
        output[pid]={'player_id':pid,'historical_teams':sorted(membership[pid]),
                     'status':'research_effects_only' if sufficient and supported else 'PASS_insufficient_or_unsupported_effects',
                     'effect_kind':VERSION,
                     'offense_effect_per_100':off if sufficient and supported else None,
                     'defense_effect_per_100':defense if sufficient and supported else None,
                     'effect_sample_possessions':min(counts['offense'],counts['defense']),
                     'exposure':dict(counts),'game_ids':sorted(games_seen[pid])}
    return {'method':VERSION,'parameters':dict(PARAMETERS),'players':output,
            'metrics_through_utc':through.isoformat(),'input_sha256':digest(archive),
            'intercept_per_100':beta[0],'home_offense_effect_per_100':beta[1],
            'solver_iterations':iterations,'training_possessions':len(events),
            'calibrated':False,'independent_validation_passed':False,
            'limitations':['Positive defense coefficient means more points allowed.',
                           'Regularization is fixed research policy, not selected on evaluation outcomes.',
                           'Collinear lineups remain confounded; coefficients are not causal on/off effects.',
                           'No replacement role, projected usage or medical status is inferred.']}
