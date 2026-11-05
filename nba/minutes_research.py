"""Chronological conditional-minute research; no active roster is inferred.

Forecast every previously observed player from prior same-team appearances,
then join current boxscore targets for scoring. This models minutes IF a player
appears, never participation, injuries, full rotations or a win probability.
"""
import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from prospective import utc
from reproducible_slate import digest


def appearances(archive):
    seen=set();games=[]
    for item in archive['games']:
        g=item['game'];gid=str(g['game_id']);tip=utc(g['tipoff_utc'])
        if gid in seen:raise ValueError('Duplicate game')
        seen.add(gid);players={}
        for p in item['players']:
            key=(p['team'],str(p['player_id']))
            if key in players or p['team'] not in (g['home_team'],g['away_team']) or str(p['game_id'])!=gid:
                raise ValueError('Duplicate or mismatched player')
            m=p['minutes_played']
            if m is not None and (type(m) not in (int,float) or not math.isfinite(m) or not 0<=m<=65):
                raise ValueError('Invalid reported minutes')
            players[key]=p
        if len({key[1] for key in players})!=len(players):raise ValueError('Player appears on both teams')
        games.append({'fixture':g,'tip':tip,'players':players})
    return sorted(games,key=lambda g:(g['tip'],str(g['fixture']['game_id'])))


def features(prior,tip,protocol):
    delay=timedelta(hours=protocol['historical_completion_delay_hours'])
    eligible=sorted((x for x in prior if x['tip']+delay<=tip),key=lambda x:(x['tip'],x['game_id']))
    if len(eligible)<protocol['minimum_prior_appearances']:return None
    values=[x['minutes'] for x in eligible[-protocol['window']:]]
    return {'x':[values[-1],sum(values[-3:])/min(3,len(values)),sum(values)/len(values),
                 min(10,len(eligible)),min(14,(tip-eligible[-1]['tip']).total_seconds()/86400)],
            'baseline':sum(values)/len(values),'last_one':values[-1],
            'prior_game_ids':[x['game_id'] for x in eligible[-protocol['window']:]],
            'latest_feature_event_tipoff_utc':eligible[-1]['tip'].isoformat()}


def episodes(archive,protocol):
    history=defaultdict(list);rows=[];coverage=[]
    for entry in appearances(archive):
        g=entry['fixture'];gid=str(g['game_id']);tip=entry['tip'];targets=entry['players']
        sides={g['home_team'],g['away_team']}
        # The forecast universe is fixed before inspecting current player rows.
        candidates={key:features(prior,tip,protocol) for key,prior in history.items() if key[0] in sides}
        score_count=0
        for key,f in sorted(candidates.items()):
            if f is None:continue
            target=targets.get(key)
            # DNP and absent rows are outside this component's conditional target.
            # They remain exclusions, never fabricated zeros or health labels.
            if not target or target['did_not_play'] or target['minutes_played'] is None:continue
            rows.append({'game_id':gid,'team':key[0],'player_id':key[1],
                         'tipoff_utc':g['tipoff_utc'],**f,'y':target['minutes_played']})
            score_count+=1
        played=[(key,p) for key,p in targets.items() if not p['did_not_play'] and p['minutes_played'] is not None]
        coverage.append({'game_id':gid,'tipoff_utc':g['tipoff_utc'],'player_rows':len(targets),
                         'recorded_appearances':len(played),'scored_appearances':score_count,
                         'below_minimum_or_missing_history':len(played)-score_count,
                         'prior_players_missing_target_row':sum(key not in targets for key,f in candidates.items() if f is not None),
                         'explicit_dnp_rows':sum(p['did_not_play'] for p in targets.values())})
        for key,p in played:
            history[key].append({'tip':tip,'game_id':gid,'minutes':p['minutes_played']})
    return rows,coverage


def solve(a,b):
    a=[list(row)+[value] for row,value in zip(a,b)];n=len(b)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]))
        if abs(a[pivot][i])<1e-12:raise ValueError('Singular fit')
        a[i],a[pivot]=a[pivot],a[i]
        scale=a[i][i];a[i]=[v/scale for v in a[i]]
        for j in range(n):
            if j==i:continue
            scale=a[j][i];a[j]=[v-scale*w for v,w in zip(a[j],a[i])]
    return [row[-1] for row in a]


def fit(rows,penalty):
    if len(rows)<10 or type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:raise ValueError('Insufficient training sample or invalid penalty')
    dimension=len(rows[0]['x']);n=len(rows)
    means=[sum(r['x'][i] for r in rows)/n for i in range(dimension)]
    scales=[math.sqrt(sum((r['x'][i]-means[i])**2 for r in rows)/n) or 1 for i in range(dimension)]
    matrix=[[0.]*(dimension+1) for _ in range(dimension+1)];target=[0.]*(dimension+1)
    for r in rows:
        x=[1]+[(v-m)/s for v,m,s in zip(r['x'],means,scales)]
        for i,v in enumerate(x):
            target[i]+=v*r['y']
            for j,w in enumerate(x):matrix[i][j]+=v*w
    for i in range(1,dimension+1):matrix[i][i]+=penalty
    return {'means':means,'scales':scales,'coefficients':solve(matrix,target),'lambda':penalty,
            'training_rows':n,'training_max_tipoff_utc':max(r['tipoff_utc'] for r in rows)}


def predict(model,x):
    if len(x)!=len(model['means']) or any(type(v) not in (int,float) or not math.isfinite(v) for v in x):raise ValueError('Invalid feature vector')
    features=[1]+[(v-m)/s for v,m,s in zip(x,model['means'],model['scales'])]
    return min(65,max(0,sum(c*v for c,v in zip(model['coefficients'],features))))


def metrics(pairs):
    if not pairs:return {'n':0,'mae':None,'rmse':None,'bias':None}
    return {'n':len(pairs),'mae':sum(abs(p-y) for p,y in pairs)/len(pairs),
            'rmse':math.sqrt(sum((p-y)**2 for p,y in pairs)/len(pairs)),
            'bias':sum(p-y for p,y in pairs)/len(pairs)}


def interval(values):
    values=sorted(values)
    def q(p):
        v=(len(values)-1)*p;i=int(v);f=v-i
        return values[i]*(1-f)+values[min(i+1,len(values)-1)]*f
    return [q(.025),q(.975)]


def uncertainty(rows,protocol):
    groups=defaultdict(list)
    for r in rows:groups[r['game_id']].append(r)
    sums=[(len(g),sum(abs(r['baseline']-r['y']) for r in g),sum(abs(r['candidate']-r['y']) for r in g),
           sum((r['baseline']-r['y'])**2 for r in g),sum((r['candidate']-r['y'])**2 for r in g)) for k,g in sorted(groups.items())]
    if len(sums)<2:return {'status':'insufficient_games','mae_gain95':None,'rmse_gain95':None}
    rng=random.Random(protocol['bootstrap_seed']);mae=[];rmse=[]
    for _ in range(protocol['bootstrap_repetitions']):
        sample=[sums[rng.randrange(len(sums))] for _ in sums];n=sum(g[0] for g in sample)
        mae.append(sum(g[1]-g[2] for g in sample)/n)
        rmse.append(math.sqrt(sum(g[3] for g in sample)/n)-math.sqrt(sum(g[4] for g in sample)/n))
    return {'status':'retrospective_game_cluster_percentile','games':len(sums),
            'repetitions':protocol['bootstrap_repetitions'],'seed':protocol['bootstrap_seed'],
            'mae_gain95':interval(mae),'rmse_gain95':interval(rmse)}


def evaluate(archive,protocol):
    if not utc(protocol['train_tipoff_before'])<utc(protocol['validation_tipoff_before'])<utc(protocol['test_tipoff_before']):raise ValueError('Invalid temporal splits')
    rows,coverage=episodes(archive,protocol)
    train=[r for r in rows if utc(r['tipoff_utc'])<utc(protocol['train_tipoff_before'])]
    validation=[r for r in rows if utc(protocol['train_tipoff_before'])<=utc(r['tipoff_utc'])<utc(protocol['validation_tipoff_before'])]
    test=[r for r in rows if utc(protocol['validation_tipoff_before'])<=utc(r['tipoff_utc'])<utc(protocol['test_tipoff_before'])]
    if not train or not validation or not test:raise ValueError('Missing temporal split')
    selection=[]
    for penalty in protocol['ridge_lambdas']:
        model=fit(train,penalty)
        selection.append({'lambda':penalty,**metrics([(predict(model,r['x']),r['y']) for r in validation])})
    chosen=min(selection,key=lambda r:(r['mae'],r['lambda']))['lambda']
    model=fit(train+validation,chosen)
    scored=[{**r,'candidate':predict(model,r['x'])} for r in test]
    result={name:metrics([(r[key],r['y']) for r in scored]) for name,key in
            (('last_five_mean','baseline'),('last_appearance','last_one'),('ridge_candidate','candidate'))}
    return {'schema_version':1,'target':protocol['target'],'protocol_sha256':digest(protocol),
            'input_sha256':digest(archive),'model':model,'model_sha256':digest(model),
            'split_rows':{'train':len(train),'validation':len(validation),'test':len(test)},
            'split_games':{name:len({r['game_id'] for r in part}) for name,part in [('train',train),('validation',validation),('test',test)]},
            'validation_selection':selection,'test_metrics':result,'paired_uncertainty':uncertainty(scored,protocol),
            'game_coverage':coverage,'test_predictions':scored,
            'conditional_component_only':True,'full_rotation_available':False,
            'independently_validated':False,'production_approved':False,'frozen_ml_modified':False,
            'limitations':['One early-season retrospective sample; source was collected after the historical games.',
                'Historical availability time is approximated by a conservative six-hour post-tip delay, not original publication timestamps.',
                'Only recorded appearances are scored; DNP, unseen roster members and playing probability are not modeled.',
                'No current-game starters, minutes or appearance flags enter feature construction.',
                'Reported total-game minutes include overtime; no regulation 240-minute allocation is claimed.',
                'Whole-game bootstrap approximates dependence; repeated-player/team dependence across games remains.',
                'No injury, replacement, position-feasibility, ML or +20 effect is inferred.']}


def markdown(r):
    out=['# NBA — modelo experimental de minutos si participa','',
         '**Evaluación retrospectiva. No es una rotación completa ni modifica ML.**','',
         '| Referencia | Apariciones de prueba | MAE (minutos) | RMSE (minutos) | Sesgo |','|---|---:|---:|---:|---:|']
    for name,m in r['test_metrics'].items():out.append(f"| {name} | {m['n']} | {m['mae']:.4f} | {m['rmse']:.4f} | {m['bias']:.4f} |")
    out+=['',f"Filas por corte: {r['split_rows']}. Partidos: {r['split_games']}. Lambda seleccionado sólo en validación: {r['model']['lambda']}.",
          '', 'Mejora positiva favorece candidato frente a media de cinco apariciones.',
          'IC95 de mejora MAE: '+str(r['paired_uncertainty']['mae_gain95']),
          'IC95 de mejora RMSE: '+str(r['paired_uncertainty']['rmse_gain95']), '',*r['limitations'],'']
    return '\n'.join(out)


def main():
    p=argparse.ArgumentParser()
    for key in ('archive','protocol','output','summary'):p.add_argument('--'+key,required=True)
    a=p.parse_args();raw=Path(a.archive).read_bytes();protocol=json.loads(Path(a.protocol).read_text())
    if hashlib.sha256(raw).hexdigest()!=protocol['input_file_sha256']:raise ValueError('Input file differs from registered research dataset')
    report=evaluate(json.loads(raw),protocol)
    for path,data in ((a.output,json.dumps(report,indent=2,allow_nan=False)),(a.summary,markdown(report))):
        with Path(path).open('x') as f:f.write(data)
    print(json.dumps({k:report[k] for k in ('split_rows','split_games','test_metrics','paired_uncertainty')},indent=2))

if __name__=='__main__':main()
