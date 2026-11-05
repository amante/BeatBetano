"""NBA 2026-27 / Challenger 2026-27.1 two-sided research orchestration.

Reuses schedule-adjusted ratings, minute allocator and digest convention.
No coefficients here are independently validated: all recommendations PASS.
"""
import argparse
import copy
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from prospective import utc
from reproducible_slate import adjusted_ratings, digest
from rotation_allocation_adapter import project_nba_minutes, allocate
from score_path import number, simulate


VERSION = 'NBA_CHALLENGER_2026_27_1_POSTMORTEM_V1'
PARAMETERS = {'minutes_response':.8, 'usage_response':1.2,
              'usage_overload_per_100':8., 'joint_role_loss_per_100':3.,
              'on_off_prior_possessions':1000., 'maximum_questionable':3}
ROLES = ('creation', 'spacing', 'rim', 'rebounding')


def no_market_fields(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ('no_odds_input','no_bookmaker_odds_as_input') and value is True:
                continue
            if any(token in key.lower() for token in ('odds', 'bookmaker', 'spread', 'implied_prob', 'moneyline')):
                raise ValueError('Market input forbidden: ' + key)
            no_market_fields(value)
    elif isinstance(node, list):
        for value in node:
            no_market_fields(value)


def verify_seal(document):
    if digest({k:v for k,v in document.items() if k != 'content_sha256'}) != document.get('content_sha256'):
        raise ValueError('Snapshot digest mismatch')


def provenance(entry, created, tip, label):
    if not isinstance(entry, dict) or entry.get('verified') is not True:
        raise ValueError('Unverified ' + label)
    source = entry.get('source_url', '')
    sha = entry.get('source_sha256', '')
    if not isinstance(source, str) or not source.startswith('https://'):
        raise ValueError('Missing source URL: ' + label)
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Missing source digest: ' + label)
    published = utc(entry['available_at_utc'])
    captured = utc(entry['observed_at_utc'])
    if not published <= captured <= created < tip:
        raise ValueError('Non-pregame evidence: ' + label)
    return captured


def validate_team(team, created, tip):
    for label in ('roster_evidence', 'injury_evidence', 'lineup_evidence', 'metrics_evidence'):
        captured = provenance(team[label], created, tip, label)
        if label != 'metrics_evidence' and (created-captured).total_seconds() > 21600:
            raise ValueError('Stale current evidence: ' + label)
    if team.get('roster_complete') is not True:
        raise ValueError('Incomplete roster')
    if utc(team['metrics_through_utc']) >= created:
        raise ValueError('Metrics window reaches snapshot')
    players = team['players']
    ids = [p['player_id'] for p in players]
    if not ids or any(not isinstance(p, str) or not p for p in ids) or len(ids) != len(set(ids)):
        raise ValueError('Duplicate or missing player IDs')
    starters = team['confirmed_starters']
    if len(starters) != 5 or len(set(starters)) != 5 or not set(starters) <= set(ids):
        raise ValueError('Unconfirmed starting five')
    for p in players:
        if p['status'] not in ('available', 'out', 'questionable'):
            raise ValueError('Unknown player availability')
        if p['player_id'] in starters and p['status'] == 'out':
            raise ValueError('Absent player in confirmed starting five')
        for field, low, high in (('baseline_minutes',0,48), ('max_minutes',0,48),
                                  ('baseline_usage',.01,.6), ('max_usage',.01,.8),
                                  ('offense_on_off',-30,30), ('defense_on_off',-30,30),
                                  ('on_off_possessions',1,1000000), ('replacement_quality',.05,3)):
            number(p[field], low, high, field)
        if p['max_usage'] < p['baseline_usage']:
            raise ValueError('Usage capacity below baseline')
        for role in ROLES:
            number(p['roles'][role],0,1,role)
    if abs(sum(p['baseline_minutes'] for p in players)-240) > .001:
        raise ValueError('Reference rotation must sum to 240')
    if abs(sum(p['baseline_minutes']/48*p['baseline_usage'] for p in players)-1) > .01:
        raise ValueError('Reference usage must conserve team possessions')
    for field, low, high in (('pace_regulation',60,140), ('turnover_rate',.01,.4),
                              ('forced_turnover_rate',.01,.4), ('transition_bonus',0,1)):
        number(team[field],low,high,field)
    number(team['path_sample_possessions'],100,1000000,'path sample')


def rotation_stints(minutes):
    """Decompose a feasible 240-minute budget into five-player court stints."""
    remaining = dict(minutes)
    time = 48.
    output = []
    while time > 1e-6:
        active = sorted(remaining, key=lambda p:(-remaining[p],p))[:5]
        if len(active) != 5 or min(remaining[p] for p in active) < 1e-8:
            raise ValueError('Cannot realize five-player rotation')
        outside = [p for p in remaining if p not in active]
        step = min([remaining[p] for p in active] + [time-remaining[p] for p in outside] + [time])
        if step <= 1e-8:
            raise ValueError('Infeasible five-player stint')
        output.append({'minutes':step, 'players':active})
        for p in active:
            remaining[p] -= step
        time -= step
    return output


def team_projection(team, assumptions):
    players = team['players']
    absent = [p for p in players if assumptions.get(p['player_id'],p['status']) == 'out']
    lost = {r:sum(p['baseline_minutes']/48*p['roles'][r] for p in absent) for r in ROLES}
    candidates = []
    for p in players:
        response = sum(p['roles'][r]*lost[r] for r in ROLES)
        weight = p['baseline_minutes']*math.exp(PARAMETERS['minutes_response']*response)*p['replacement_quality']
        # Quality affects only redistributed minutes: retain reference weight when healthy.
        if not absent:
            weight = p['baseline_minutes']
        candidates.append({'player_id':p['player_id'],
                           'status':assumptions.get(p['player_id'],p['status']),
                           'expected_weight':weight, 'max_units':p['max_minutes']})
    result = project_nba_minutes({'roster_complete':True, 'availability_source_verified':True, 'players':candidates})
    minutes = result.get('allocations')
    if minutes is None:
        raise ValueError('Infeasible minutes: ' + result['status'])
    usage = []
    for p in players:
        pid = p['player_id']
        load = sum(p['roles'][r]*lost[r] for r in ROLES)
        usage.append({'player_id':pid,'status':'available' if minutes[pid] else 'out',
                      'expected_weight':minutes[pid]*p['baseline_usage']*math.exp(PARAMETERS['usage_response']*load),
                      'max_units':minutes[pid]/48*p['max_usage']})
    shares = allocate('nba','targets',usage,total=1).get('allocations')
    if shares is None:
        raise ValueError('Insufficient creation/usage capacity')
    offense = defense = overload = 0.
    rows = []
    for p in players:
        pid = p['player_id']
        fraction = minutes[pid]/48
        u = shares[pid]/fraction if fraction else 0.
        shrink = p['on_off_possessions']/(p['on_off_possessions']+PARAMETERS['on_off_prior_possessions'])
        shift = (minutes[pid]-p['baseline_minutes'])/48
        offense += shift*p['offense_on_off']*shrink
        # Defensive on/off is allowed-points delta: negative is better.
        defense += shift*p['defense_on_off']*shrink
        overload += fraction*max(0,u-p['baseline_usage'])**2
        rows.append({'player_id':pid,'status':assumptions.get(pid,p['status']),
                     'minutes':minutes[pid],'usage':u,'team_possession_share':shares[pid],
                     'minute_delta':minutes[pid]-p['baseline_minutes'],
                     'replacement_quality':p['replacement_quality'],'on_off_reliability':shrink})
    # Only residual uncovered roles are penalized, quadratically and jointly.
    residual = {r:max(0,lost[r]-sum(max(0,minutes[p['player_id']]-p['baseline_minutes'])/48*p['roles'][r]
                                     for p in players)) for r in ROLES}
    joint = PARAMETERS['joint_role_loss_per_100']*sum(v*v for v in residual.values())
    offense -= PARAMETERS['usage_overload_per_100']*overload + joint
    defense += joint/2
    stints = rotation_stints(minutes)
    by_id = {p['player_id']:p for p in players}
    if any(sum(by_id[p]['roles']['creation'] for p in s['players']) < .5 or
           sum(by_id[p]['roles']['rim'] for p in s['players']) < .5 for s in stints):
        raise ValueError('Rotation lacks creation or rim coverage')
    return {'players':rows,'rotation_stints':stints,'lost_roles':lost,'uncovered_roles':residual,
            'offense_delta_per_100':offense,'defense_delta_per_100':defense,
            'nonlinear_joint_penalty_per_100':joint,'usage_overload':overload,
            'assumptions':assumptions}


def matchup(game, teams, ratings, assumptions, simulations, seed):
    names = (game['home_team'],game['away_team'])
    rotations = {t:team_projection(teams[t],assumptions.get(t,{})) for t in names}
    projections = {}
    pace = sum(teams[t]['pace_regulation'] for t in names)/2
    for i, t in enumerate(names):
        opp = names[1-i]
        own = ratings[t]
        ortg = own['opponent_adjusted_ortg'] + rotations[t]['offense_delta_per_100']
        drtg = own['opponent_adjusted_drtg'] + rotations[t]['defense_delta_per_100']
        rival_d = ratings[opp]['opponent_adjusted_drtg'] + rotations[opp]['defense_delta_per_100']
        # Ratings already contain historical turnovers. Add only matchup deltas.
        baseline_ppp = (ortg+rival_d-own['league_rating'])/100
        q = (teams[t]['turnover_rate']+teams[opp]['forced_turnover_rate'])/2
        forced = (teams[opp]['turnover_rate']+teams[t]['forced_turnover_rate'])/2
        non_to_ppp = baseline_ppp/(1-teams[t]['turnover_rate'])
        delta = -(q-teams[t]['turnover_rate'])*non_to_ppp
        delta += (forced-teams[t]['forced_turnover_rate'])*(1-q)*teams[t]['transition_bonus']
        ppp = baseline_ppp+delta
        conditional_after_to = ppp + (1-forced)*(1-q)*teams[t]['transition_bonus']
        projections[t] = {'availability_adjusted_ortg':ortg,'availability_adjusted_drtg':drtg,
                          'possessions':pace,'ppp':ppp,'regulation_points':pace*ppp,
                          'turnover_rate':q,'expected_turnovers':pace*q,
                          'turnover_pressure_delta_ppp':delta,
                          'points_after_opponent_turnovers':pace*forced*conditional_after_to,
                          'transition_bonus':teams[t]['transition_bonus'],
                          'non_turnover_blocks':teams[t]['non_turnover_blocks']}
    path = simulate(projections[names[0]],projections[names[1]],pace,simulations,seed)
    for t in names:
        blocks = projections[t].pop('non_turnover_blocks')
        projections[t]['offensive_explosiveness'] = {
            'observed_blocks':len(blocks),
            'eight_plus_points_in_four_non_turnover_possessions':sum(sum(b)>=8 for b in blocks)/len(blocks)}
    return {'teams':rotations,'projections':projections,'path':path}


def build(snapshot, evidence, boxscores, simulations=4000, seed=2026271, emitted_at=None):
    verify_seal(snapshot)
    no_market_fields(snapshot)
    no_market_fields(evidence)
    no_market_fields(boxscores)
    if evidence.get('snapshot_sha256') != snapshot['content_sha256']:
        raise ValueError('Evidence belongs to another baseline snapshot')
    created = utc(snapshot['created_at_utc'])
    emitted = utc(emitted_at) if emitted_at else datetime.now(timezone.utc)
    if emitted < created:
        raise ValueError('Source cutoff is after actual emission')
    fixtures = snapshot['predictions']
    ids = [str(g['game_id']) for g in fixtures]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Empty or duplicate slate')
    if set(evidence.get('games',{}))-set(ids):
        raise ValueError('Unexpected evidence fixtures')
    # The existing schedule residual estimator is shared, not reimplemented.
    ratings = adjusted_ratings(boxscores,snapshot['created_at_utc'])
    output = []
    for g in fixtures:
        tip = utc(g['tipoff_utc'])
        if created >= tip or g['home_team'] == g['away_team']:
            raise ValueError('Invalid pregame fixture')
        gid = str(g['game_id'])
        baseline = {}
        for name in ('elo','challenger','hybrid'):
            p = number(g[name+'_p_home'],0,1,'baseline probability')
            baseline[name] = {'home_ml':p,'away_ml':1-p,'home_plus20':None,'away_plus20':None}
        row = {'game_id':gid,'home_team':g['home_team'],'away_team':g['away_team'],
               'tipoff_utc':g['tipoff_utc'],'baseline':baseline,'challenger':None,
               'on_off_scenarios':[], 'recommendation':'PASS', 'eligible_for_bet':False,
               'final_probabilities':None,'missing':[]}
        teams = evidence.get('games',{}).get(gid,{}).get('teams',{})
        try:
            if set(teams)-{g['home_team'],g['away_team']}:
                raise ValueError('Unexpected team evidence')
            material_errors = []
            for t in (g['home_team'],g['away_team']):
                try:
                    if t not in teams:
                        raise ValueError('Missing verified roster, injuries, lineups, player effects and score-path evidence')
                    validate_team(teams[t],created,tip)
                    for key in ('opponent_adjusted_ortg','opponent_adjusted_drtg'):
                        number(ratings[t][key],60,180,key)
                except (KeyError, TypeError, ValueError) as exc:
                    material_errors.append(t+': '+str(exc))
            if material_errors:
                raise ValueError('; '.join(material_errors))
            home_ids = {p['player_id'] for p in teams[g['home_team']]['players']}
            away_ids = {p['player_id'] for p in teams[g['away_team']]['players']}
            if home_ids & away_ids:
                raise ValueError('Player assigned to both opponents')
            uncertain = [(t,p['player_id']) for t in (g['home_team'],g['away_team'])
                         for p in teams[t]['players'] if p['status'] == 'questionable']
            if len(uncertain) > PARAMETERS['maximum_questionable']:
                raise ValueError('Too many joint availability branches')
            if uncertain:
                for choices in itertools.product(('available','out'),repeat=len(uncertain)):
                    assumptions = {t:{} for t in teams}
                    for (t,p),state in zip(uncertain,choices):
                        assumptions[t][p] = state
                    branch = {'assumptions':assumptions,'scenario_weight':None,'forecast':None}
                    try:
                        branch['forecast'] = matchup(g,teams,ratings,assumptions,simulations,seed)
                    except ValueError as exc:
                        branch['missing'] = str(exc)
                    row['on_off_scenarios'].append(branch)
                row['missing'].append('Unresolved availability; scenarios are not probability-weighted')
            else:
                row['challenger'] = matchup(g,teams,ratings,{},simulations,seed)
                healthy = {t:{p['player_id']:'available' for p in teams[t]['players']}
                           for t in (g['home_team'],g['away_team'])}
                try:
                    reference = matchup(g,teams,ratings,healthy,simulations,seed)
                    row['all_available_counterfactual'] = reference
                    row['availability_delta'] = {
                        'probabilities':{k:v-reference['path']['probabilities'][k]
                                         for k,v in row['challenger']['path']['probabilities'].items()},
                        'regulation_points':{t:row['challenger']['projections'][t]['regulation_points']-
                                               reference['projections'][t]['regulation_points'] for t in healthy},
                        'note':'Hypothetical all-available comparison, not a confirmed healthy lineup'}
                except ValueError as exc:
                    row['counterfactual_missing'] = str(exc)
                row['challenger_minus_baseline'] = {
                    k:row['challenger']['path']['probabilities']['home_ml']-v['home_ml'] for k,v in baseline.items()}
            row['missing'].append('Independent injury/replacement and score-path holdout validation')
        except (KeyError,TypeError,ValueError) as exc:
            row['missing'].append(str(exc))
        output.append(row)
    # Deep freeze by serialization: later caller mutations cannot rewrite evidence.
    report = {'schema_version':1,'model_version':VERSION,'created_at_utc':emitted.isoformat(),
              'prediction_as_of_utc':snapshot['created_at_utc'],
              'emission_kind':'pregame' if all(emitted < utc(g['tipoff_utc']) for g in fixtures) else 'retrospective_replay',
              'baseline_snapshot_sha256':snapshot['content_sha256'],
              'parameters':copy.deepcopy(PARAMETERS),'parameters_sha256':digest(PARAMETERS),
              'simulation_settings':{'simulations':simulations,'seed':seed},
              'inputs':{'baseline':snapshot,'evidence':evidence,'boxscores':boxscores},
              'games':output,'calibrated':False,'production_approved':False,
              'no_bookmaker_odds_as_input':True}
    report = json.loads(json.dumps(report,allow_nan=False))
    report['content_sha256'] = digest(report)
    return report


def save_new(path, report):
    verify_seal(report)
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation; settlement always writes a separate report.
    with path.open('x') as target:
        json.dump(report,target,indent=2,allow_nan=False)


def main():
    parser = argparse.ArgumentParser()
    for name in ('snapshot','evidence','boxscores','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--simulations',type=int,default=4000)
    parser.add_argument('--seed',type=int,default=2026271)
    args = parser.parse_args()
    load = lambda p:json.loads(Path(p).read_text())
    result = build(load(args.snapshot),load(args.evidence),load(args.boxscores),args.simulations,args.seed)
    save_new(args.output,result)
    print(json.dumps({'games':len(result['games']),'recommendation':'PASS',
                      'content_sha256':result['content_sha256']}))


if __name__ == '__main__':
    main()
