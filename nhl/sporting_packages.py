"""Connect observed goalie counts to quantitative research; no invented CRS or PP/PK."""
import argparse
import json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc


def build(report,crosswalk,history,rosters,analysis_as_of):
    cutoff=parse_utc(analysis_as_of)
    capture=parse_utc(report['generated_at_utc'])
    if cutoff<capture:raise ValueError('Analysis precedes source capture')
    h={str(g['game_id']):g for g in history['games']}
    if len(h)!=len(history['games']):raise ValueError('Duplicate history fixture')
    if history.get('kind')!='nhl_candidate_goalie_history_251' or parse_utc(history['as_of_utc'])!=capture:raise ValueError('History contract mismatch')
    roster_index={r['team']:r for r in rosters}
    if len(roster_index)!=len(rosters):raise ValueError('Duplicate roster')
    packages={};excluded=[]
    for f in report['games']:
        gid=str(f['game_id']);sides={};start=parse_utc(f['start_utc'])
        if not capture<=cutoff<start:raise ValueError('Analysis must precede puck drop')
        g=h.get(gid)
        if g and (g['home'],g['away'])!=(f['home'],f['away']):raise ValueError('History identity mismatch')
        for team in (f['home'],f['away']):
            sides[team]={}
            source=(g or {}).get('teams',{}).get(team,{})
            obs=[o for o in crosswalk.get('observations',[]) if str(o.get('nhl_game_id',o.get('game_id')))==gid and o.get('team')==team and o.get('usable_pregame_identity') is True and not o.get('validation_errors')]
            if len(obs)!=1 or source.get('status')!='observed' or source.get('nhl_player_id')!=obs[0].get('nhl_player_id'):
                excluded.append(dict(game_id=gid,team=team,reason='missing_unique_goalie_identity_or_history'));continue
            ob=obs[0];pid=ob['nhl_player_id'];roster=roster_index.get(team)
            found=[p for p in (roster or {}).get('players',[]) if p.get('player_id')==pid and p.get('position_group')=='goalie']
            if len(found)!=1:raise ValueError('Goalie ID not independently matched to official roster')
            if not parse_utc(roster['as_of'])<=parse_utc(ob['source_captured_at'])<=capture:raise ValueError('Identity source chronology mismatch')
            meta=source['source'];m=source['metrics'];stats=m['season_to_date'];observed=parse_utc(meta['retrieved_at'])
            if not capture<=observed<=cutoff:raise ValueError('Goalie history outside analysis capture window')
            if m['cutoff_exclusive']!=capture.date().isoformat():raise ValueError('History includes wrong date cutoff')
            if not meta['url'].startswith('https://api-web.nhle.com/v1/player/'+str(pid)+'/game-log/') or len(meta.get('sha256',''))!=64:raise ValueError('Unattributed goalie history')
            saves,shots,games=(stats[k] for k in ('saves','shots_against','games'))
            if any(type(x) is not int for x in (saves,shots,games)) or not 0<=saves<=shots or shots<=0 or games<=0:raise ValueError('Invalid observed goalie counts')
            sides[team]['goalie']=dict(goalie_player_id=pid,identity_independently_verified=True,starter_independently_confirmed=False,source_url=meta['url'],source_sha256=meta['sha256'],as_of=meta['retrieved_at'],prior_saves=saves,prior_shots=shots,prior_games=games,history_cutoff_exclusive=m['cutoff_exclusive'],provider_status=ob.get('goalie_status'))
        packages[gid]=sides
    return packages,excluded


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('report','crosswalk','history','rosters','analysis-as-of','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();read=lambda field:json.loads(Path(getattr(a,field)).read_text())
    packages,excluded=build(read('report'),read('crosswalk'),read('history'),read('rosters')['rosters'],a.analysis_as_of)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(packages,indent=2))
    print(json.dumps(dict(connected_goalie_sides=sum('goalie' in t for g in packages.values() for t in g.values()),excluded=excluded)))
