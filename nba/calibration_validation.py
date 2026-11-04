"""Descriptive NBA calibration and paired, calendar-clustered uncertainty.

No recalibration, coefficient selection, independent-validation certification or
production promotion is performed by this module.
"""
import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from model import evaluate
from challenger import predict_challenger
from clean_regular import clean


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def wilson(wins,n):
    if n==0:return None
    z=1.959963984540054
    p=wins/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-half),min(1,center+half)]


def calibration(pairs):
    if not pairs:raise ValueError('Nonempty predictions required')
    for p,y in pairs:
        if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1 or type(y) is not int or y not in (0,1):
            raise ValueError('Finite interior probability and binary outcome required')
    n=len(pairs);bins=[]
    for i in range(10):
        selected=[(p,y) for p,y in pairs if min(int(p*10),9)==i]
        k=len(selected)
        mean=sum(p for p,y in selected)/k if k else None
        wins=sum(y for p,y in selected)
        rate=wins/k if k else None
        bins.append({'lower':i/10,'upper':(i+1)/10,'n':k,'mean_forecast':mean,
                     'observed_rate':rate,'observed_rate_wilson95':wilson(wins,k),
                     'absolute_gap':abs(mean-rate) if k else None})
    return {'n':n,'brier':sum((p-y)**2 for p,y in pairs)/n,
            'log_loss':-sum(y*math.log(p)+(1-y)*math.log1p(-p) for p,y in pairs)/n,
            'accuracy':sum(int(p>=.5)==y for p,y in pairs)/n,
            'mean_forecast':sum(p for p,y in pairs)/n,'observed_rate':sum(y for p,y in pairs)/n,
            'mean_bias':sum(p-y for p,y in pairs)/n,
            'ece_10_equal_width':sum(b['n']*(b['absolute_gap'] or 0) for b in bins)/n,
            'maximum_bin_gap':max(b['absolute_gap'] or 0 for b in bins),
            'reliability_bins':bins,'calibrated_certified':False}


def quantile(sorted_values,p):
    x=(len(sorted_values)-1)*p;i=int(x);f=x-i
    return sorted_values[i]*(1-f)+sorted_values[min(i+1,len(sorted_values)-1)]*f


def paired_bootstrap(rows,repetitions=2000,seed=20261104,unit='week'):
    """Resample whole league date/week clusters; retain pairing and season strata.

    CI is percentile bootstrap of game-weighted mean loss gains, positive when
    Challenger improves. Not adjusted for model selection or long-range team
    dependence; day and week results are sensitivity analyses, not independent tests.
    """
    if not rows or type(repetitions) is not int or repetitions<100 or unit not in ('day','week'):
        raise ValueError('Need rows, >=100 replicates and day/week clusters')
    by_season=defaultdict(lambda:defaultdict(list))
    for r in rows:
        day=datetime.fromisoformat(r['league_date']).date()
        cluster=day.isoformat() if unit=='day' else day.isocalendar()[:2]
        e,c,y=r['elo'],r['challenger'],r['y']
        # Validate the same domain used in calibration before taking logarithms.
        calibration([(e,y),(c,y)])
        gains=((e-y)**2-(c-y)**2,
               -y*math.log(e)-(1-y)*math.log1p(-e)+y*math.log(c)+(1-y)*math.log1p(-c))
        by_season[r['season']][cluster].append(gains)
    groups=[]
    for season in sorted(by_season):
        clusters=by_season[season]
        groups.append([(len(v),sum(x[0] for x in v),sum(x[1] for x in v)) for k,v in sorted(clusters.items())])
    totals=[g for season in groups for g in season]
    n=sum(g[0] for g in totals)
    point=[sum(g[i] for g in totals)/n for i in (1,2)]
    rng=random.Random(seed);draws=[[],[]]
    for _ in range(repetitions):
        picked=[season[rng.randrange(len(season))] for season in groups for j in range(len(season))]
        count=sum(g[0] for g in picked)
        for k,i in enumerate((1,2)):draws[k].append(sum(g[i] for g in picked)/count)
    return {'unit':unit,'clusters':len(totals),'repetitions':repetitions,'seed':seed,
            'season_stratified':True,'paired_same_games':True,
            **{name:{'gain_elo_minus_challenger':point[k],
                      'percentile95':[quantile(sorted(draws[k]),p) for p in (.025,.975)]}
               for k,name in enumerate(('brier','log_loss'))}}


def prediction_rows(history):
    if len({str(g['game_id']) for g in history})!=len(history):raise ValueError('Duplicate games')
    if {int(g['season']) for g in history}!={2024,2025,2026}:raise ValueError('Exactly seasons ending 2024/2025/2026 required')
    games,audit=clean(history)
    if len(games)!=3690 or not audit['coverage_verified']:raise ValueError('Incomplete historical coverage')
    games=sorted(games,key=lambda g:(g['tipoff_utc'],str(g['game_id'])))
    base=list(evaluate(games,season_min=2024,season_max=2026));candidate=predict_challenger(games)
    rows=[]
    for g,e,c in zip(games,base,candidate):
        if g['season'] not in (2025,2026):continue
        t=datetime.fromisoformat(g['tipoff_utc'].replace('Z','+00:00'))
        if t.tzinfo is None:raise ValueError('Timezone required')
        rows.append({'game_id':str(g['game_id']),'season':g['season'],'tipoff_utc':g['tipoff_utc'],
                     'league_date':t.astimezone(ZoneInfo('America/New_York')).date().isoformat(),
                     'elo':e.p_home,'challenger':c['p_home'],'y':int(g['home_points']>g['away_points'])})
    return rows


def evaluate_history(history,repetitions=2000,seed=20261104):
    rows=prediction_rows(history)
    groups={str(s):[r for r in rows if r['season']==s] for s in (2025,2026)}
    groups['pooled']=rows
    return {'schema_version':1,'history_sha256':sha(history),'prediction_rows_sha256':sha(rows),
            'warmup_season_end':2024,'scored_games':len(rows),
            'evaluation_type':'retrospective_descriptive_not_independent_certification',
            'groups':{name:{'elo':calibration([(r['elo'],r['y']) for r in sample]),
                            'challenger':calibration([(r['challenger'],r['y']) for r in sample]),
                            'paired_uncertainty':{unit:paired_bootstrap(sample,repetitions,seed,unit) for unit in ('week','day')}}
                      for name,sample in groups.items()},
            'limitations':['Weekly clustering only approximates schedule and within-team dependence.',
                          'Wilson bin intervals assume Bernoulli independence and are descriptive; they are not dependence-adjusted.',
                          'ECE depends on fixed binning and finite sample; no automatic pass threshold is applied.',
                          'Bootstrap intervals do not correct post-selection bias or establish untouched holdout provenance.',
                          'No fitted calibration is evaluated on these same games.'],
            'independent_validation_passed':False,'automatic_promotion_allowed':False,
            'no_odds_input':True}


def markdown(report):
    lines=['# NBA — Calibración e incertidumbre retrospectivas','',
           '**No constituye certificación independiente ni promoción del modelo.**','',
           '| Temporada final | n | Brier Elo / Challenger | Log loss Elo / Challenger | ECE Elo / Challenger | Mejora Brier, IC95 semanal |',
           '|---|---:|---:|---:|---:|---|']
    for label,g in report['groups'].items():
        e,c=g['elo'],g['challenger'];gain=g['paired_uncertainty']['week']['brier']
        lo,hi=gain['percentile95']
        lines.append(f"| {label} | {e['n']} | {e['brier']:.6f} / {c['brier']:.6f} | {e['log_loss']:.6f} / {c['log_loss']:.6f} | {e['ece_10_equal_width']:.6f} / {c['ece_10_equal_width']:.6f} | {gain['gain_elo_minus_challenger']:.6f} [{lo:.6f}, {hi:.6f}] |")
    lines += ['','Mejora positiva favorece Challenger. IC por remuestreo emparejado de semanas, estratificado por temporada. Sensibilidad diaria y bins completos en JSON.','']
    for label,g in report['groups'].items():
        for model in ('elo','challenger'):
            lines += [f'## {label} — {model}', '', '| Rango | n | Probabilidad media | Frecuencia observada | Wilson 95% descriptivo |','|---|---:|---:|---:|---|']
            for b in g[model]['reliability_bins']:
                fmt=lambda v:'—' if v is None else f'{v:.4f}'
                ci=b['observed_rate_wilson95']
                interval='—' if ci is None else f'[{ci[0]:.4f}, {ci[1]:.4f}]'
                lines.append(f"| {b['lower']:.1f}–{b['upper']:.1f} | {b['n']} | {fmt(b['mean_forecast'])} | {fmt(b['observed_rate'])} | {interval} |")
    lines += ['',*report['limitations'],'']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser()
    for name in ('history','output','summary'):p.add_argument('--'+name,required=True)
    p.add_argument('--repetitions',type=int,default=2000)
    a=p.parse_args();history=json.loads(Path(a.history).read_text())
    history=[g for g in history if int(g['season']) in (2024,2025,2026)]
    report=evaluate_history(history,a.repetitions)
    for path,body in ((a.output,json.dumps(report,indent=2,allow_nan=False)),(a.summary,markdown(report))):
        with Path(path).open('x') as f:f.write(body)
    print(json.dumps({k:{'brier_gain':v['paired_uncertainty']['week']['brier'],'ece_challenger':v['challenger']['ece_10_equal_width']} for k,v in report['groups'].items()},indent=2))

if __name__=='__main__':main()
