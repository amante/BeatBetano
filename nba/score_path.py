"""Odds-free empirical block bootstrap for ML and reaching +20, including OT.

Blocks retain short scoring runs. Mean tilting and turnover pressure are research
hypotheses, not fitted or independently calibrated probability estimates.
"""
import math
import random


def number(value, low, high, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Invalid ' + label)
    return float(value)


def tilted_blocks(blocks, mean):
    """Exponential tilt of whole blocks; preserve within-block scoring order."""
    if not isinstance(blocks, list) or len(blocks) < 3:
        raise ValueError('Need at least three observed scoring blocks')
    if any(not isinstance(b, list) or len(b) != 4 for b in blocks):
        raise ValueError('Scoring blocks must contain four non-turnover possessions')
    for b in blocks:
        for x in b:
            if type(x) is not int or not 0 <= x <= 4:
                raise ValueError('Invalid observed possession points')
    means = [sum(b)/4 for b in blocks]
    if not min(means) < mean < max(means):
        raise ValueError('Projected scoring mean outside empirical block support')
    def weights(lam):
        logits = [lam * sum(b) for b in blocks]
        pivot = max(logits)
        return [math.exp(v-pivot) for v in logits]
    lo, hi = -64., 64.
    for _ in range(70):
        mid = (lo+hi)/2
        w = weights(mid)
        current = sum(v*m for v,m in zip(w,means))/sum(w)
        if current < mean:
            lo = mid
        else:
            hi = mid
    w = weights((lo+hi)/2)
    total = sum(w)
    cumulative = []
    for value in w:
        cumulative.append((cumulative[-1] if cumulative else 0) + value/total)
    cumulative[-1] = 1.
    return cumulative


def sample_block(rng, blocks, cumulative):
    u = rng.random()
    for b, c in zip(blocks, cumulative):
        if u <= c:
            return list(b)
    raise AssertionError('Invalid CDF')


def lead_events(scores):
    """Observe every scoring event, including between alternating possessions."""
    home = away = 0
    max_home = max_away = 0
    for side, points in scores:
        if side == 0:
            home += points
        elif side == 1:
            away += points
        else:
            raise ValueError('Unknown scoring side')
        max_home = max(max_home, home-away)
        max_away = max(max_away, away-home)
    return home, away, max_home, max_away


def simulate(home, away, possessions, simulations=4000, seed=2026271):
    """Inputs: ppp, turnover_rate, transition_bonus, non_turnover_blocks.

    Conditional kernels conserve projected unconditional PPP. The transition
    bonus changes scoring after an opponent turnover without counting it twice.
    ML is a final-score outcome; reaching +20 is a first-passage event.
    """
    if type(simulations) is not int or not 100 <= simulations <= 100000:
        raise ValueError('Simulation count outside [100, 100000]')
    if type(seed) is not int:
        raise ValueError('Integer seed required')
    pace = number(possessions, 60, 140, 'projected possessions')
    teams = [home, away]
    kernels = []
    for i, t in enumerate(teams):
        ppp = number(t['ppp'], .3, 2.5, 'PPP')
        q = number(t['turnover_rate'], .01, .4, 'turnover rate')
        bonus = number(t['transition_bonus'], 0, 1, 'transition bonus')
        opponent_q = number(teams[1-i]['turnover_rate'], .01, .4, 'opponent turnovers')
        normal = ppp/(1-q) - opponent_q*bonus
        blocks = t['non_turnover_blocks']
        kernels.append([tilted_blocks(blocks, normal), tilted_blocks(blocks, normal+bonus)])
    rng = random.Random(seed)
    counts = {'home_ml':0, 'away_ml':0, 'home_plus20':0, 'away_plus20':0,
              'either_plus20':0, 'both_plus20':0}
    totals = [0, 0]
    overtime_games = 0
    for _ in range(simulations):
        points = [0, 0]
        leads = [False, False]
        queues = [[[], []], [[], []]]
        last_turnover = [False, False]
        first = rng.randrange(2)
        def play(n):
            for __ in range(n):
                for side in (first, 1-first):
                    t = teams[side]
                    turnover = rng.random() < t['turnover_rate']
                    if not turnover:
                        context = int(last_turnover[1-side])
                        if not queues[side][context]:
                            queues[side][context] = sample_block(rng, t['non_turnover_blocks'], kernels[side][context])
                        points[side] += queues[side][context].pop(0)
                    last_turnover[side] = turnover
                    leads[side] |= points[side]-points[1-side] >= 20
        # Randomized integer rounding preserves expected regulation pace.
        play(int(pace) + int(rng.random() < pace-int(pace)))
        overtime = 0
        while points[0] == points[1]:
            overtime += 1
            if overtime > 30:
                raise ValueError('Unresolved overtime; refusing biased tie disposal')
            ot_pace = pace*5/48
            play(max(1,int(ot_pace)+int(rng.random() < ot_pace-int(ot_pace))))
        overtime_games += int(overtime > 0)
        counts['home_ml' if points[0] > points[1] else 'away_ml'] += 1
        for side, name in enumerate(('home_plus20', 'away_plus20')):
            counts[name] += int(leads[side])
        counts['either_plus20'] += int(any(leads))
        counts['both_plus20'] += int(all(leads))
        totals = [s+p for s,p in zip(totals,points)]
    probabilities = {k:v/simulations for k,v in counts.items()}
    return {'probabilities':probabilities,
            'monte_carlo_se':{k:math.sqrt(p*(1-p)/simulations) for k,p in probabilities.items()},
            'mean_points_including_overtime':dict(zip(('home','away'),(x/simulations for x in totals))),
            'simulations':simulations, 'seed':seed, 'includes_overtime':True,
            'overtime_games':overtime_games,
            'method':'empirical_four_possession_block_tilt_v1', 'calibrated':False}
