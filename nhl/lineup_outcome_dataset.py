"""Join immutable pregame lineup records to final labels without duplicate games."""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def build(captures,postmortems):
    labels={};selected={};excluded=[]
    for report in postmortems:
        if report.get('kind')!='nhl_daily_postmortem':raise ValueError('Postmortem required')
        for game in report.get('games',[]):
            if game.get('state') not in ('OFF','FINAL'):continue
            gid=str(game['game_id']);outcome=game.get('outcomes',{}).get('ml_winner')
            if outcome not in ('home','away'):continue
            value=dict(home=game['home'],away=game['away'],start_utc=game['start_utc'],ml_winner=outcome)
            if gid in labels and labels[gid]!=value:raise ValueError('Conflicting final labels')
            labels[gid]=value
    for capture in captures:
        if capture.get('kind')!='nhl_frozen_lineup_dataset_v1':raise ValueError('Frozen lineup capture required')
        for row in capture['records']:
            gid=str(row['game_id']);stamp=parse_utc(row['frozen_at_utc']);start=parse_utc(row['start_utc'])
            if stamp>=start:raise ValueError('Post-start features rejected')
            if not row.get('complete_observed_inputs'):
                excluded.append(dict(game_id=gid,reason='incomplete_inputs'));continue
            prior=selected.get(gid)
            if prior and any(prior[k]!=row[k] for k in ('home','away','start_utc')):raise ValueError('Conflicting fixture identity')
            if prior is None or stamp<parse_utc(prior['frozen_at_utc']):selected[gid]=row
            elif stamp==parse_utc(prior['frozen_at_utc']) and row!=prior:raise ValueError('Conflicting same-time features')
    rows=[]
    for gid,row in sorted(selected.items(),key=lambda item:(item[1]['start_utc'],item[0])):
        label=labels.get(gid)
        if label is None:excluded.append(dict(game_id=gid,reason='final_label_pending'));continue
        if any(label[k]!=row[k] for k in ('home','away','start_utc')):raise ValueError('Label fixture mismatch')
        rows.append(dict(game_id=gid,start_utc=row['start_utc'],feature_as_of_utc=row['frozen_at_utc'],home=row['home'],away=row['away'],features=row['teams'],target_ml_home=int(label['ml_winner']=='home')))
    return dict(kind='nhl_lineup_labeled_dataset_v1',selection_policy='earliest complete pregame capture per game',rows=rows,excluded=excluded,training_approved=False,probabilities_modified=False,limitations=['Labels are postgame targets only.','Dataset availability does not establish predictive improvement.','Temporal validation and comparison against the same-game baseline remain required.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--captures',default='nhl/learning/lineups');p.add_argument('--postmortems',default='frontend/data/nhl-postmortems');p.add_argument('--output',required=True);a=p.parse_args()
    load=lambda folder:[json.loads(f.read_text()) for f in sorted(Path(folder).glob('*.json'))]
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);result=build(load(a.captures),load(a.postmortems));out.write_text(json.dumps(result,indent=2));print(json.dumps(dict(labeled_games=len(result['rows']),excluded=len(result['excluded']))))
