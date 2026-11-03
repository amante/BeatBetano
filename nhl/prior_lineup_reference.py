"""Observed previous-game participation; never a projected or confirmed next lineup."""
import argparse,gzip,json,hashlib
from pathlib import Path
from nhl.special_teams_capture import fetch
from nhl.pulso_pregame_v7 import parse_utc

def participants(payload,team,game_id):
    if str(payload.get('id'))!=str(game_id) or payload.get('gameState') not in ('OFF','FINAL'):raise ValueError('Wrong or unfinished reference game')
    side=next((s for s in ('home','away') if payload.get(s+'Team',{}).get('abbrev')==team),None)
    if not side:raise ValueError('Reference team mismatch')
    rows=payload['playerByGameStats'][side+'Team'];players=[];seen=set()
    for group,role in [('forwards','forward'),('defense','defense'),('goalies','goalie')]:
        if not isinstance(rows.get(group),list):raise ValueError('Missing player group')
        for p in rows[group]:
            pid=p['playerId'];parts=p.get('toi','').split(':')
            if type(pid) is not int or pid<=0 or pid in seen:raise ValueError('Invalid or duplicate player')
            seen.add(pid)
            if len(parts)!=2 or not all(v.isdigit() for v in parts) or int(parts[1])>=60:raise ValueError('Missing valid TOI')
            seconds=int(parts[0])*60+int(parts[1])
            if not seconds:continue
            players.append(dict(player_id=pid,name=p.get('name',{}).get('default'),role=role,observed_toi_seconds=seconds))
    return dict(team=team,game_id=str(game_id),players=players,reference_type='previous_completed_game_participation',expected_lineup=False,applied_to_probability=False)

def collect(context,get=fetch):
    if context.get('kind')!='nhl_official_schedule_context_v1':raise ValueError('Official schedule context required')
    games=[];raws={};cache={}
    for fixture in context['games']:
        teams={}
        for team,prior in fixture['teams'].items():
            try:
                if prior.get('status')!='observed_schedule_context':raise ValueError('No completed previous fixture')
                gid=str(prior['previous_game_id'])
                if not gid.isdigit():raise ValueError('Invalid reference game ID')
                if gid not in cache:cache[gid]=get('https://api-web.nhle.com/v1/gamecenter/'+gid+'/boxscore')
                raw,at=cache[gid]
                if parse_utc(at)<parse_utc(context['as_of_utc']) or parse_utc(at)>=parse_utc(fixture['start_utc']):raise ValueError('Reference retrieval outside pregame window')
                x=participants(json.loads(raw),team,gid);x['source']=dict(url='https://api-web.nhle.com/v1/gamecenter/'+gid+'/boxscore',retrieved_at=at,sha256=hashlib.sha256(raw).hexdigest())
                teams[team]=x;raws[gid]=raw.decode()
            except (OSError,ValueError,KeyError,TypeError) as e:teams[team]=dict(status='missing_reference',reason=str(e)[:160],applied_to_probability=False)
        games.append(dict(game_id=fixture['game_id'],teams=teams))
    return dict(kind='nhl_prior_lineup_reference_v1',games=games,applied_to_probability=False,limitations=['Previous-game participants are not the next expected lineup.','Observed TOI is not an asserted prospective deployment share.','Absence from this reference does not establish injury.']),raws

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--context',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result,raw=collect(json.loads(Path(a.context).read_text()));out=Path(a.output);out.write_text(json.dumps(result,indent=2));out.with_suffix('.sources.json.gz').write_bytes(gzip.compress(json.dumps(raw).encode(),mtime=0))
