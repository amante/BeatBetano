"""Regularized independent Poisson attack/defence with home advantage."""
import math


def fit(rows, penalty=0.01, iterations=6000):
    if not rows or penalty <= 0:
        raise ValueError('Training rows and positive regularization required')
    teams = sorted({r[t] for r in rows for t in ('home', 'away')})
    idx = {t: i for i, t in enumerate(teams)}
    n, k = len(rows), len(teams)
    samples = [(idx[r['home']], idx[r['away']], r['hg'], r['ag']) for r in rows]
    x = [math.log(max(sum(r['ag'] for r in rows) / n, .01)), 0.] + [0.] * (2*k)
    def objective(v, gradient=False):
        g = [0.] * len(v)
        loss = 0.
        for h, a, yh, ya in samples:
            eh, ea = v[0]+v[1]+v[2+h]-v[2+k+a], v[0]+v[2+a]-v[2+k+h]
            lh, la = math.exp(eh), math.exp(ea)
            loss += (lh-yh*eh+la-ya*ea)/n
            rh, ra = (lh-yh)/n, (la-ya)/n
            g[0] += rh+ra; g[1] += rh
            g[2+h] += rh; g[2+a] += ra
            g[2+k+a] -= rh; g[2+k+h] -= ra
        for j in range(2, len(v)):
            loss += penalty*v[j]*v[j]/2
            g[j] += penalty*v[j]
        return loss, g
    converged = False
    for step in range(iterations):
        loss, g = objective(x)
        norm = sum(z*z for z in g)
        if norm < 1e-12:
            converged = True
            break
        rate = 1.
        for _ in range(30):
            candidate = [v-rate*z for v, z in zip(x, g)]
            for start in (2, 2+k):
                mean = sum(candidate[start:start+k])/k
                for j in range(start, start+k): candidate[j] -= mean
            new_loss, _ = objective(candidate)
            if new_loss <= loss - 1e-4*rate*norm: break
            rate /= 2
        else:
            raise RuntimeError('Optimizer line search failed')
        x = candidate
    if not converged:
        raise RuntimeError('Optimizer did not converge')
    return dict(teams=idx, coefficients=x, penalty=penalty, trained_through=max(r['date'] for r in rows), iterations=step)


def goal_distribution(rate):
    if not math.isfinite(rate) or not 0 < rate <= 100:
        raise ValueError('Unsupported goal rate')
    p = [math.exp(-rate)]
    while 1-sum(p) > 1e-10:
        p.append(p[-1]*rate/len(p))
    return p


def predict(model, home, away, date):
    if date <= model['trained_through']:
        raise ValueError('Prediction must follow all training dates')
    idx, v = model['teams'], model['coefficients']
    k = len(idx)
    def effect(team, offset): return v[offset+idx[team]] if team in idx else 0.
    lh = math.exp(v[0]+v[1]+effect(home, 2)-effect(away, 2+k))
    la = math.exp(v[0]+effect(away, 2)-effect(home, 2+k))
    hp, ap = goal_distribution(lh), goal_distribution(la)
    probs = [0., 0., 0.]
    for h, ph in enumerate(hp):
        for a, pa in enumerate(ap): probs[0 if h > a else 1 if h == a else 2] += ph*pa
    mass = sum(probs)
    return dict(probabilities=[p/mass for p in probs], expected_goals=[lh, la], omitted_mass=1-mass, unknown_teams=[t for t in (home, away) if t not in idx])


def frequency(rows):
    counts = [1., 1., 1.]
    for r in rows: counts[0 if r['hg'] > r['ag'] else 1 if r['hg'] == r['ag'] else 2] += 1
    return [c/sum(counts) for c in counts]


def metrics(predictions, rows):
    brier = logloss = correct = 0.
    for p, r in zip(predictions, rows):
        y = 0 if r['hg'] > r['ag'] else 1 if r['hg'] == r['ag'] else 2
        brier += sum((q-int(i == y))**2 for i, q in enumerate(p))
        logloss -= math.log(max(p[y], 1e-15))
        correct += max(range(3), key=lambda i: p[i]) == y
    n = len(rows)
    if not n or len(predictions) != n: raise ValueError('One prediction per result required')
    return dict(games=n, brier_sum=brier/n, log_loss=logloss/n, accuracy=correct/n)
