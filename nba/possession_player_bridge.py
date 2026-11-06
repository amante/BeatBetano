"""Bind verified normalized possession/lineup exports to the sporting research engine.

This is not a raw ESPN shot parser. An incomplete raw play feed never becomes a
possession archive merely because its final score reconciles.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from player_possession_effects import fit
from possession_path_features import extract
from postmortem_engine import build, no_market_fields, provenance, save_new, validate_team, verify_seal
from prospective import utc
from reproducible_slate import digest

PATH_FIELDS=('path_sample_possessions','pace_regulation','turnover_rate',
             'forced_turnover_rate','transition_bonus','non_turnover_blocks')
EFFECT_FIELDS=('effect_kind','offense_effect_per_100','defense_effect_per_100','effect_sample_possessions')


def connect(snapshot, archive, context):
    verify_seal(snapshot)
    no_market_fields(context)
    if context.get('snapshot_sha256') != snapshot['content_sha256']:
        raise ValueError('Player context belongs to another snapshot')
    expected={str(g['game_id']) for g in snapshot['predictions']}
    if set(context.get('games',{}))-expected:
        raise ValueError('Unexpected context fixtures')
    evidence={'snapshot_sha256':snapshot['content_sha256'],'games':{}}
    report={'schema_version':1,'snapshot_sha256':snapshot['content_sha256'],
            'created_at_utc':datetime.now(timezone.utc).isoformat(),
            'context_sha256':digest(context),'archive_sha256':digest(archive) if archive is not None else None,
            'games':[], 'recommendation':'PASS','production_approved':False}
    if not snapshot['predictions']:raise ValueError('Empty fixture slate')
    tipoff=min((g['tipoff_utc'] for g in snapshot['predictions']),key=utc)
    created=snapshot['created_at_utc']
    paths=effects=None
    shared_missing=[]
    if archive is None:
        shared_missing.append('Missing verified normalized possession/lineup export')
    else:
        no_market_fields(archive)
        try:
            # Root provenance covers the normalized export and its lineup attribution.
            provenance(archive['evidence'],utc(created),utc(tipoff),'normalized possession export')
            paths=extract(archive,created,tipoff)
            effects=fit(archive,created,tipoff)
        except (KeyError,TypeError,ValueError) as exc:
            shared_missing.append(str(exc))
        report['path_features']=paths
        report['player_effects']=effects
    for game in snapshot['predictions']:
        gid=str(game['game_id'])
        source=context.get('games',{}).get(gid,{}).get('teams',{})
        team_rows=[]
        if set(source)-{game['home_team'],game['away_team']}:
            raise ValueError('Unexpected context team')
        for team in (game['home_team'],game['away_team']):
            missing=list(shared_missing)
            candidate=copy.deepcopy(source.get(team,{}))
            if not candidate:missing.append('Missing verified roster/availability/rotation/role context')
            if paths is not None and effects is not None and candidate:
                path=paths['teams'].get(team,{})
                if path.get('status') != 'research_features_only':
                    missing.append('Insufficient normalized possession sample for '+team)
                else:
                    candidate.update({key:path[key] for key in PATH_FIELDS})
                for player in candidate.get('players',[]):
                    effect=effects['players'].get(player['player_id'],{})
                    if effect.get('status') != 'research_effects_only':
                        missing.append('Missing supported adjusted effect for '+player['player_id'])
                    else:
                        # Never keep a conflicting legacy effect alongside the new definition.
                        for key in ('offense_on_off','defense_on_off','on_off_possessions'):
                            player.pop(key,None)
                        player.update({key:effect[key] for key in EFFECT_FIELDS})
                candidate['metrics_through_utc']=effects['metrics_through_utc']
                candidate['metrics_evidence']=copy.deepcopy(archive['evidence'])
                candidate['feature_derivation']={'archive_sha256':digest(archive),
                    'effect_method':effects['method'],'fit_parameters':copy.deepcopy(effects['parameters']),
                    'path_extractor':'possession_path_features.extract',
                    'additional_engine_shrinkage':True}
                if not missing:
                    try:validate_team(candidate,utc(created),utc(game['tipoff_utc']))
                    except (KeyError,TypeError,ValueError) as exc:missing.append(str(exc))
            if not missing:
                evidence['games'].setdefault(gid,{'teams':{}})['teams'][team]=candidate
            team_rows.append({'team':team,'inputs_connected':not missing,'missing':missing})
        report['games'].append({'game_id':gid,'teams':team_rows,'recommendation':'PASS'})
    report['connected_games']=sum(all(t['inputs_connected'] for t in g['teams']) for g in report['games'])
    report['evidence_sha256']=digest(evidence)
    report['content_sha256']=digest(report)
    return evidence,report


def main():
    parser=argparse.ArgumentParser()
    for field in ('snapshot','context','boxscores','output-dir'):
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--possessions')
    parser.add_argument('--simulations',type=int,default=4000)
    args=parser.parse_args()
    load=lambda name:json.loads(Path(name).read_text())
    snapshot=load(args.snapshot)
    archive=load(args.possessions) if args.possessions else None
    context=load(args.context)
    evidence,audit=connect(snapshot,archive,context)
    sporting=build(snapshot,evidence,load(args.boxscores),simulations=args.simulations)
    root=Path(args.output_dir)
    root.mkdir(parents=True,exist_ok=False)
    for name,value in (('evidence',evidence),('bridge',audit),('sporting',sporting)):
        if name=='evidence':value={**value,'content_sha256':digest(value)}
        save_new(root/(name+'.json'),value)
    inputs={'archive':archive,'context':context}
    inputs['content_sha256']=digest(inputs)
    save_new(root/'source-inputs.json',inputs)
    print(json.dumps({'games':len(sporting['games']),'connected_games':audit['connected_games'],
                      'recommendation':'PASS'}))


if __name__=='__main__':main()
