"""Experimental NFL joint opportunity simulation. No production integration.

Scenario inputs must be estimated from pregame sports data, not betting odds.
The model samples whole games, then evaluates every leg against the same draw.
"""
import math
import random
from collections import Counter
from multisport.data_lineage import verify_manifest, digest, utc
from multisport.calibration_audit import score

MARKETS = {'pass_yards', 'receiving_yards', 'receptions', 'rush_yards', 'carries',
           'tackles', 'snaps', 'targets', 'longest_reception_50_plus'}


def number(x, low=0, high=float('inf')):
    if type(x) not in (int, float) or not math.isfinite(x) or not low <= x <= high:
        raise ValueError('Invalid finite numeric input')
    return x


def validate(config, legs):
    verify_manifest(config['manifest'])
    teams = config['teams']
    if len(teams) != 2 or len(set(teams)) != 2:
        raise ValueError('Exactly two teams required')
    players = config['players']
    ids = [p['player_id'] for p in players]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Unique players required')
    for p in players:
        if p['team'] not in teams or p['position'] not in ('QB', 'WR', 'TE', 'RB', 'DEF'):
            raise ValueError('Invalid team/position')
        # Availability is already resolved in this experiment; uncertain cases
        # must be represented by separate, externally weighted configurations.
        if p.get('status') not in ('available', 'out'):
            raise ValueError('Resolve availability first')
        for key in ('snap_share', 'catch_rate', 'explosive_rate'):
            number(p[key], 0, 1)
        for key in ('target_weight', 'carry_weight', 'tackle_weight'):
            number(p[key])
        number(p['yards_per_catch'], .01, 49)
        number(p['yards_per_carry'], .01, 30)
    for team in teams:
        active = [p for p in players if p['team'] == team and p['status'] == 'available']
        if sum(p['position'] == 'QB' and p['snap_share'] == 1 for p in active) != 1:
            raise ValueError('One full-game QB per team required')
        if any(p['position'] == 'QB' and p['snap_share'] != 1 for p in active):
            raise ValueError('Partial/multiple QB scenarios unsupported')
        for key in ('target_weight', 'carry_weight', 'tackle_weight'):
            if not any(p[key] > 0 and p['snap_share'] > 0 for p in active):
                raise ValueError('Full receiving/rushing/defense coverage required')
    scenarios = config['scenarios']
    if not scenarios or abs(sum(number(s['weight'], 0, 1) for s in scenarios)-1) > 1e-8:
        raise ValueError('Scenario weights must sum to one')
    for s in scenarios:
        if not s.get('game_script'):
            raise ValueError('Named game script required')
        number(s['pace_factor'], .5, 1.5)
        number(s['weather_factor'], 0, 1)
        number(s['tackle_probability'], 0, 1)
        for team in teams:
            number(s['plays'][team], 1, 150)
            number(s['pass_rate'][team], 0, 1)
    if not 1 <= len(legs) <= 13:
        raise ValueError('BetBuilder requires 1..13 legs')
    signatures = set()
    for leg in legs:
        if leg['player_id'] not in ids or leg['market'] not in MARKETS:
            raise ValueError('Unknown player/market')
        if leg['market'] == 'longest_reception_50_plus':
            if leg['op'] != 'is' or type(leg['value']) is not bool:
                raise ValueError('50+ reception is strictly binary')
        elif leg['op'] not in ('ge', 'le'):
            raise ValueError('Numeric legs require ge/le')
        else:
            number(leg['value'])
        key = (leg['player_id'], leg['market'], leg['op'], leg['value'])
        if key in signatures:
            raise ValueError('Duplicate leg')
        signatures.add(key)


def choose(rng, players, key, snaps):
    eligible = [p for p in players if snaps[p['player_id']] > 0 and p[key] > 0]
    weights = [p[key]*snaps[p['player_id']] for p in eligible]
    if not eligible:
        return None
    return rng.choices(eligible, weights=weights, k=1)[0]


def draw(config, rng):
    scenario = rng.choices(config['scenarios'], weights=[s['weight'] for s in config['scenarios']], k=1)[0]
    stats = {p['player_id']: {m: (False if m == 'longest_reception_50_plus' else 0) for m in MARKETS} for p in config['players']}
    rosters = {t: [p for p in config['players'] if p['team'] == t and p['status'] == 'available'] for t in config['teams']}
    plays = {t: max(1, min(150, round(rng.gauss(scenario['plays'][t]*scenario['pace_factor'], 5)))) for t in rosters}
    for team, players in rosters.items():
        for p in players:
            # Shared team volume; role uncertainty introduces positive covariance
            # in opportunities without independent prop draws.
            volume = plays[next(t for t in rosters if t != team)] if p['position'] == 'DEF' else plays[team]
            stats[p['player_id']]['snaps'] = sum(rng.random() < p['snap_share'] for _ in range(volume))
    for team, players in rosters.items():
        opponent = next(t for t in rosters if t != team)
        qb = next(p['player_id'] for p in players if p['position'] == 'QB')
        # Integer participation budgets enforce targets/carries <= actual snaps.
        remaining = {p['player_id']: stats[p['player_id']]['snaps'] for p in players}
        defenders = rosters[opponent]
        defensive_remaining = {p['player_id']: stats[p['player_id']]['snaps'] for p in defenders}
        for _ in range(plays[team]):
            if rng.random() < scenario['pass_rate'][team]:
                receiver = choose(rng, players, 'target_weight', remaining)
                if receiver:
                    pid = receiver['player_id']; remaining[pid] -= 1
                    stats[pid]['targets'] += 1
                    if rng.random() < receiver['catch_rate']*scenario['weather_factor']:
                        stats[pid]['receptions'] += 1
                        explosive = rng.random() < receiver['explosive_rate']*scenario['weather_factor']
                        yards = rng.uniform(50, 99) if explosive else min(49.999, rng.expovariate(1/receiver['yards_per_catch']))
                        stats[pid]['receiving_yards'] += yards
                        stats[qb]['pass_yards'] += yards
                        stats[pid]['longest_reception_50_plus'] |= explosive
            else:
                runner = choose(rng, players, 'carry_weight', remaining)
                if runner:
                    pid = runner['player_id']; remaining[pid] -= 1
                    stats[pid]['carries'] += 1
                    stats[pid]['rush_yards'] += min(99, rng.expovariate(1/runner['yards_per_carry']))
            if rng.random() < scenario['tackle_probability']:
                defender = choose(rng, defenders, 'tackle_weight', defensive_remaining)
                if defender:
                    pid = defender['player_id']; defensive_remaining[pid] -= 1
                    stats[pid]['tackles'] += 1
    return stats


def hit(stats, leg):
    value = stats[leg['player_id']][leg['market']]
    return value == leg['value'] if leg['op'] == 'is' else (value >= leg['value'] if leg['op'] == 'ge' else value <= leg['value'])


def simulate(config, legs, samples=10000, seed=42):
    validate(config, legs)
    if type(samples) is not int or samples < 100:
        raise ValueError('At least 100 simulation draws required')
    rng = random.Random(seed)
    counts, joint, patterns = [0]*len(legs), 0, Counter()
    for _ in range(samples):
        stats = draw(config, rng)
        hits = [hit(stats, leg) for leg in legs]
        for i, passed in enumerate(hits):
            counts[i] += passed
        joint += all(hits)
        patterns[''.join('1' if h else '0' for h in hits)] += 1
    p = joint/samples
    # Wilson interval stays informative when there are zero observed joint hits.
    z = 1.96; denom = 1+z*z/samples
    center = (p+z*z/(2*samples))/denom
    radius = z*math.sqrt(p*(1-p)/samples+z*z/(4*samples*samples))/denom
    marginals = [n/samples for n in counts]
    independent = math.prod(marginals)
    return {'joint_probability': p, 'marginal_probabilities': marginals,
            'independence_probability': independent, 'joint_minus_independence': p-independent,
            'joint_mc_interval95': [max(0, center-radius), min(1, center+radius)],
            'hit_patterns': dict(patterns), 'samples': samples, 'seed': seed,
            'input_sha256': digest(config), 'legs_sha256': digest(legs),
            'calibrated': False, 'official_model_changed': False,
            'warning': 'Monte Carlo error only; scenario/parameter/model uncertainty is not covered'}


def historical_audit(records):
    """Score archived joint forecasts vs independence, by holdout season.

    No fitting on evaluation outcomes. Chronological calibration may be supplied
    externally, with its training cutoff preceding each frozen forecast.
    """
    if not records:
        raise ValueError('Historical joint outcomes required')
    seen, groups = set(), {}
    for r in records:
        verify_manifest(r['manifest'])
        key = (r['event_id'], r['builder_id'])
        if key in seen:
            raise ValueError('Duplicate builder')
        seen.add(key)
        if utc(r['training_cutoff_utc']) >= utc(r['manifest']['prediction_as_of_utc']):
            raise ValueError('Calibration training leakage')
        if utc(r['settled_at_utc']) < utc(r['manifest']['event_start_utc']):
            raise ValueError('Outcome settled before kickoff')
        if type(r['outcome']) is not int or r['outcome'] not in (0, 1):
            raise ValueError('Joint outcome must be binary')
        for name in ('joint_probability', 'independence_probability'):
            number(r[name], 0, 1)
        groups.setdefault(r['season'], []).append(r)
    return {'by_season': {str(s): {name: score([(r[name], r['outcome']) for r in rows]) for name in ('joint_probability', 'independence_probability')} for s, rows in groups.items()},
            'calibrated': False, 'automatic_promotion_allowed': False,
            'note': 'Descriptive joint reliability; builders within games are dependent. Requires independent season review.'}


def main():
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='JSON {config, legs} or audit record list')
    parser.add_argument('--output', required=True)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--samples', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text())
    result = historical_audit(payload) if args.audit else simulate(payload['config'], payload['legs'], args.samples, args.seed)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
