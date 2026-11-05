"""Chronological, paired scoring of frozen postmortem forecasts; never refit.

Real archived pregame evidence is mandatory for a prospective claim. Digest
validation alone cannot prove that a timestamp was recorded before the game.
"""
import argparse
import json
import math
from datetime import timedelta
from pathlib import Path

from postmortem_engine import verify_seal, provenance, VERSION
from prospective import utc
from reproducible_slate import digest


def metrics(pairs):
    n = len(pairs)
    if not n:
        return {'n':0,'brier':None,'log_loss':None,'calibration':[]}
    bins = []
    for i in range(10):
        sample = [(p,y) for p,y in pairs if min(9,int(p*10)) == i]
        if sample:
            bins.append({'bin':i,'n':len(sample),'mean_probability':sum(p for p,y in sample)/len(sample),
                         'observed_rate':sum(y for p,y in sample)/len(sample)})
    return {'n':n,'brier':sum((p-y)**2 for p,y in pairs)/n,
            'log_loss':-sum(y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p)) for p,y in pairs)/n,
            'calibration':bins}


def evaluate(snapshots, results):
    if not isinstance(results, list):
        raise ValueError('Expected results list')
    outcomes = {str(g['game_id']):g for g in results}
    if len(outcomes) != len(results):
        raise ValueError('Duplicate outcomes')
    seen = set()
    rows = []
    exclusions = []
    versions = set()
    for report in sorted(snapshots,key=lambda s:utc(s['created_at_utc'])):
        verify_seal(report)
        if report['model_version'] != VERSION:
            raise ValueError('Unexpected model version')
        if digest(report['parameters']) != report['parameters_sha256']:
            raise ValueError('Parameter digest mismatch')
        versions.add(report['parameters_sha256'])
        created = utc(report['created_at_utc'])
        if utc(report['prediction_as_of_utc']) > created:
            raise ValueError('Feature cutoff after emission')
        for g in sorted(report['games'],key=lambda x:(utc(x['tipoff_utc']),x['game_id'])):
            gid = str(g['game_id'])
            if gid in seen:
                raise ValueError('Multiple emissions for one fixture; preregister selection before scoring')
            seen.add(gid)
            tip = utc(g['tipoff_utc'])
            if created >= tip:
                raise ValueError('Post-start forecast')
            result = outcomes.get(gid)
            if result is None:
                exclusions.append({'game_id':gid,'reason':'missing_outcome'})
                continue
            if any(result[k] != g[k] for k in ('home_team','away_team')) or utc(result['tipoff_utc']) != tip:
                raise ValueError('Outcome fixture identity mismatch')
            # Outcome evidence is postgame, checked against its own observation.
            observed = utc(result['evidence']['observed_at_utc'])
            if not tip < utc(result['completed_at_utc']) <= observed:
                raise ValueError('Invalid completion timestamp')
            provenance(result['evidence'],observed,observed+timedelta(seconds=1),'outcome')
            hp, ap = result['home_points'],result['away_points']
            if any(type(v) is not int or not 0 <= v <= 300 for v in (hp,ap)) or hp == ap:
                raise ValueError('Invalid final NBA score')
            forecast = g.get('challenger')
            if forecast is None:
                exclusions.append({'game_id':gid,'reason':'missing_material_inputs_or_unresolved_scenarios'})
                continue
            probs = forecast['path']['probabilities']
            if any(type(p) not in (int,float) or not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
                raise ValueError('Invalid probability')
            row = {'game_id':gid,'tipoff_utc':g['tipoff_utc'],'snapshot_sha256':report['content_sha256'],
                   'home_ml_outcome':int(hp > ap), 'candidate':probs,'baseline':g['baseline'],
                   'home_plus20_outcome':None,'away_plus20_outcome':None}
            # Final margin cannot substitute for maximum in-game leads.
            if result.get('score_path_complete') is True:
                for side, lower, upper in (('home',max(0,hp-ap),hp),('away',max(0,ap-hp),ap)):
                    lead = result[side+'_max_lead']
                    if type(lead) is not int or not lower <= lead <= upper:
                        raise ValueError('Invalid maximum lead')
                    row[side+'_plus20_outcome'] = int(lead >= 20)
            rows.append(row)
    if len(versions) > 1:
        raise ValueError('Mixed parameter versions; evaluate separately')
    rows.sort(key=lambda x:(utc(x['tipoff_utc']),x['game_id']))
    pooled = {}
    for side in ('home','away'):
        key = side+'_ml'
        y = lambda r:r['home_ml_outcome'] if side == 'home' else 1-r['home_ml_outcome']
        pooled[key] = {'challenger':metrics([(r['candidate'][key],y(r)) for r in rows])}
        for label in ('elo','challenger','hybrid'):
            pooled[key][label+'_baseline'] = metrics([(r['baseline'][label][key],y(r)) for r in rows])
        key = side+'_plus20'
        eligible = [r for r in rows if r[key+'_outcome'] is not None]
        pooled[key] = {'challenger':metrics([(r['candidate'][key],r[key+'_outcome']) for r in eligible]),
                       'baseline':None,'baseline_missing_reason':'No frozen baseline path probabilities'}
    return {'model_version':VERSION,'fixtures_expected':len(seen),'scored_ml_games':len(rows),
            'unmatched_outcome_ids':sorted(set(outcomes)-seen),'excluded':exclusions,
            'metrics':pooled,'chronological_games':rows,
            'independent_holdout_validation_passed':False,'production_approved':False,
            'limitations':['Frozen snapshot scoring does not establish independent calibration.',
                           'No retrospective reconstruction of missing pregame availability.',
                           'No model fitting or coefficient selection occurs during scoring.',
                           'Timestamp and digest checks require external pretip publication provenance.']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshots',nargs='+',required=True)
    p.add_argument('--results',required=True)
    p.add_argument('--output',required=True)
    a = p.parse_args()
    load = lambda f:json.loads(Path(f).read_text())
    result = evaluate([load(f) for f in a.snapshots],load(a.results))
    with Path(a.output).open('x') as target:
        json.dump(result,target,indent=2,allow_nan=False)
    print(json.dumps({'expected':result['fixtures_expected'],'scored':result['scored_ml_games']}))


if __name__ == '__main__':
    main()
