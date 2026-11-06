"""Auditable walk-forward experiments; never changes registry or production models.

The predictor factory receives only settled history and an explicit feature allowlist.
Snapshots use first-write-only files: an existing event/version cannot be overwritten.
"""
import json
from copy import deepcopy
import math
from pathlib import Path
from multisport.data_lineage import utc, verify_manifest, digest
from multisport.calibration_audit import score
from multisport.model_registry import SPORTS


def snapshot(record, directory):
    verify_manifest(record['manifest'])
    if not record.get('event_id') or not record.get('model_version'):
        raise ValueError('Event and version required')
    p = record['probabilities']
    if not p or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in p.values()):
        raise ValueError('Invalid probabilities')
    # Identity excludes mutable content so a changed forecast cannot replace its freeze.
    identity = digest([record['event_id'], record['model_version']])
    payload = json.dumps(record, sort_keys=True, allow_nan=False)
    path = Path(directory) / (identity + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(payload)
    return {'path': str(path), 'sha256': digest(record)}


def validate_events(events):
    if not events:
        raise ValueError('Nonempty events required')
    seen = set()
    for e in events:
        key = (e['sport'], e['market'], e['event_id'])
        if key in seen or e['sport'] not in SPORTS:
            raise ValueError('Duplicate event or unsupported sport')
        seen.add(key)
        verify_manifest(e['manifest'])
        if utc(e['settled_at_utc']) < utc(e['manifest']['event_start_utc']):
            raise ValueError('Outcome settled before start')
        if type(e['outcome']) is not int or e['outcome'] not in (0, 1):
            raise ValueError('Binary outcomes required; encode 1X2 as separate one-v-rest markets')
        if not e.get('season'):
            raise ValueError('Season required')
    if len({(e['sport'], e['market']) for e in events}) != 1:
        raise ValueError('Evaluate one sport/market per experiment')


def walk_forward(events, factory, feature_names, ablations=None):
    """Refit per forecast using outcomes settled strictly before its freeze.

    factory(history, feature_names) -> predictor(features). History has no external
    references; no test outcome or non-allowlisted field is passed to the predictor.
    All learned preprocessing/calibration must live inside factory. Sports inputs
    must be enumerated explicitly; arbitrary feature names are not safety proof.
    """
    validate_events(events)
    names = tuple(feature_names)
    if not names or len(set(names)) != len(names):
        raise ValueError('Unique sports feature allowlist required')
    variants = {'challenger': names}
    for name, removed in (ablations or {}).items():
        if name in ('baseline', 'challenger') or not name or not set(removed) <= set(names):
            raise ValueError('Invalid ablation')
        variants[name] = tuple(k for k in names if k not in removed)
    rows = []
    ordered = sorted(events, key=lambda e: (utc(e['manifest']['prediction_as_of_utc']), e['event_id']))
    for event in ordered:
        freeze = utc(event['manifest']['prediction_as_of_utc'])
        past = [e for e in ordered if utc(e['settled_at_utc']) < freeze]
        # Beta(1,1) empirical sports-event frequency; no odds, current labels or priors fitted on holdout.
        predictions = {'baseline': (1 + sum(e['outcome'] for e in past)) / (2 + len(past))}
        for name, features in variants.items():
            history = [dict(features={k: e['features'][k] for k in features}, outcome=e['outcome'],
                            season=e['season'], event_id=e['event_id']) for e in past]
            predictor = factory(deepcopy(history), features)
            probability = predictor(deepcopy({k: event['features'][k] for k in features}))
            if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError('Invalid predictor probability')
            predictions[name] = probability
        rows.append({'event_id': event['event_id'], 'season': event['season'],
                     'prediction_as_of_utc': event['manifest']['prediction_as_of_utc'],
                     'training_event_ids': [e['event_id'] for e in past],
                     'outcome': event['outcome'], 'probabilities': predictions})
    return rows


def evaluate(rows, holdout_seasons, min_games=100, required_ablations=()):
    """Fixed independent seasons only; thresholds must be selected before running.

    Eligibility is a conservative screening signal, not statistical significance
    or permission to promote. Requires improvement in both metrics in every season.
    """
    seasons = list(holdout_seasons)
    if min_games < 1 or len(set(seasons)) != len(seasons) or not seasons:
        raise ValueError('Invalid holdout protocol')
    if len(set(required_ablations)) != len(required_ablations) or set(required_ablations) & {'baseline', 'challenger'}:
        raise ValueError('Distinct ablation names required')
    variants = {'baseline', 'challenger', *required_ablations}
    identities = set()
    for row in rows:
        identity = row['event_id']
        if identity in identities:
            raise ValueError('Duplicate evaluation event')
        identities.add(identity)
        if type(row['outcome']) is not int or row['outcome'] not in (0, 1):
            raise ValueError('Invalid evaluation outcome')
        for p in row['probabilities'].values():
            if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError('Invalid evaluation probability')
    metrics, reasons = {}, []
    if len(seasons) < 2:
        reasons.append('two_independent_seasons_required')
    if not required_ablations:
        reasons.append('ablations_required')
    for season in seasons:
        sample = [r for r in rows if r['season'] == season]
        if len(sample) < min_games:
            reasons.append(f'insufficient_games:{season}')
        if not sample:
            continue
        if any(not variants <= r['probabilities'].keys() for r in sample):
            reasons.append(f'incomplete_paired_variants:{season}')
            continue
        metrics[str(season)] = {v: score([(r['probabilities'][v], r['outcome']) for r in sample]) for v in sorted(variants)}
        m = metrics[str(season)]
        for v in variants - {'challenger'}:
            if any(m['challenger'][k] >= m[v][k] for k in ('brier', 'log_loss')):
                reasons.append(f'no_consistent_gain:{season}:{v}')
    return {'by_season': metrics, 'screening_passed': not reasons, 'reasons': reasons,
            'automatic_promotion_allowed': False,
            'requires_independent_lineage_and_reliability_review': True}


def elo_factory(history, feature_names):
    """Odds-free participant-strength baseline for resolved binary winner markets.

    Features: home_id/away_id. For tennis these mean player A/B; no home advantage
    is applied. Ties/draws require a separate market model, not fabricated wins.
    """
    if set(feature_names) != {'home_id', 'away_id'}:
        raise ValueError('Elo requires participant ids only')
    ratings = {}
    for row in history:
        h, a = row['features']['home_id'], row['features']['away_id']
        p = 1 / (1 + 10 ** ((ratings.get(a, 1500)-ratings.get(h, 1500))/400))
        delta = 20 * (row['outcome']-p)
        ratings[h] = ratings.get(h, 1500)+delta
        ratings[a] = ratings.get(a, 1500)-delta
    def predict(features):
        h, a = features['home_id'], features['away_id']
        return 1 / (1 + 10 ** ((ratings.get(a, 1500)-ratings.get(h, 1500))/400))
    return predict
