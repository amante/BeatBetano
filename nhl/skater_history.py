"""Prior-day official skater game logs; observed counts, no probability effect."""
from datetime import date

def summarize(player_id, payload, cutoff_day):
    cutoff=date.fromisoformat(cutoff_day)
    if type(player_id) is not int or player_id<=0:raise ValueError('Invalid player ID')
    rows=payload.get('gameLog')
    if not isinstance(rows,list):raise ValueError('Missing game log')
    seen=set();goals=shots=seconds=games=0
    assists=pim=0;assists_complete=pim_complete=True
    for row in rows:
        day=date.fromisoformat(row['gameDate'])
        if day>=cutoff:continue
        gid=row['gameId']
        if gid in seen:raise ValueError('Duplicate game')
        seen.add(gid)
        g,s=row.get('goals'),row.get('shots')
        if any(type(v) is not int or v<0 for v in (g,s)) or g>s:raise ValueError('Invalid counts')
        parts=row.get('toi','').split(':')
        if len(parts)!=2 or not all(x.isdigit() for x in parts):raise ValueError('Missing or invalid TOI')
        minutes,secs=map(int,parts)
        if secs>=60:raise ValueError('Invalid TOI seconds')
        for key in ('assists','pim'):
            value=row.get(key)
            if value is not None and (type(value) is not int or value<0):raise ValueError('Invalid '+key)
            if key=='assists':
                assists_complete &= value is not None;assists+=value or 0
            else:
                pim_complete &= value is not None;pim+=value or 0
        goals+=g;shots+=s;seconds+=minutes*60+secs;games+=1
    return dict(player_id=player_id,role='skater',skater_games=games,skater_goals=goals,skater_shots=shots,skater_assists=assists if assists_complete else None,penalty_minutes=pim if pim_complete else None,toi_games=games,toi_seconds=seconds,cutoff_exclusive=cutoff_day,applied_to_probability=False)

def collect(report,rosters,fetcher=None,reference=None):
    from concurrent.futures import ThreadPoolExecutor
    from nhl.pulso_goalie_history_251 import fetch,season_for
    from nhl.pulso_pregame_v7 import parse_utc
    fetcher=fetcher or fetch
    at=parse_utc(report['generated_at_utc'])
    if report.get('data_kind')!='source_readiness_only' or report.get('official_predictions')!=0:raise ValueError('Source report required')
    teams={t for g in report['games'] for t in (g['home'],g['away'])}
    starts={t:min(parse_utc(g['start_utc']) for g in report['games'] if t in (g['home'],g['away'])) for t in teams}
    pool={};seen=set()
    for roster in rosters['rosters']:
        team=roster['team']
        if team not in teams:continue
        if team in seen:raise ValueError('Duplicate roster')
        seen.add(team)
        if parse_utc(roster['as_of'])>at or not roster.get('source_url','').startswith('https://api-web.nhle.com/'):raise ValueError('Invalid roster provenance')
        for player in roster['players']:
            if player.get('position_group')=='goalie':continue
            pid=player['player_id']
            if type(pid) is not int or pid<=0:raise ValueError('Invalid player ID')
            pool.setdefault(pid,set()).add(team)
    if reference is not None:
        if reference.get('kind')!='nhl_prior_lineup_reference_v1':raise ValueError('Invalid prior reference')
        fixtures={str(g['game_id']):g for g in report['games']}
        for game in reference['games']:
            fixture=fixtures.get(str(game['game_id']))
            if fixture is None:raise ValueError('Reference fixture mismatch')
            for team,side in game['teams'].items():
                if team not in (fixture['home'],fixture['away']):raise ValueError('Reference team mismatch')
                if not side.get('players'):continue
                source=side['source']
                if parse_utc(source['retrieved_at'])>=starts[team] or not source['url'].startswith('https://api-web.nhle.com/v1/gamecenter/'):raise ValueError('Invalid reference source')
                for player in side['players']:
                    if player['role']=='goalie':continue
                    pid=player['player_id']
                    if type(pid) is not int or pid<=0:raise ValueError('Invalid reference player')
                    pool.setdefault(pid,set()).add(team)
    season=season_for(at.date().isoformat());cutoff=at.date().isoformat()
    def one(item):
        pid,clubs=item
        try:
            payload,source=fetcher(pid,season)
            stamp=parse_utc(source['retrieved_at'])
            if stamp<at or any(stamp>=starts[t] for t in clubs):raise ValueError('Source outside pregame capture window')
            if source['url']!=f'https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2':raise ValueError('Unexpected history source')
            return str(pid),dict(summarize(pid,payload,cutoff),source=source,identity_candidate_teams=sorted(clubs)),payload,None
        except (OSError,ValueError,KeyError,TypeError) as e:return str(pid),None,None,str(e)[:160]
    with ThreadPoolExecutor(max_workers=4) as executor:rows=list(executor.map(one,pool.items()))
    return dict(kind='nhl_skater_history_capture_v1',source_capture_as_of=report['generated_at_utc'],season=season,cutoff_exclusive=cutoff,players={pid:r for pid,r,_,e in rows if e is None},errors={pid:e for pid,_,_,e in rows if e is not None},missing_roster_teams=sorted(teams-seen),applied_to_probability=False,limitations=['Roster identity is not an expected lineup.','Historical TOI is not expected deployment.','Independent baseline lineup and fitted player effects remain required.']),{pid:p for pid,_,p,e in rows if e is None}

if __name__=='__main__':
    import argparse,gzip,json
    from pathlib import Path
    p=argparse.ArgumentParser()
    for name in ('report','rosters','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--reference')
    a=p.parse_args();result,raw=collect(json.loads(Path(a.report).read_text()),json.loads(Path(a.rosters).read_text()),reference=json.loads(Path(a.reference).read_text()) if a.reference else None)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));out.with_suffix('.sources.json.gz').write_bytes(gzip.compress(json.dumps(raw).encode(),mtime=0))
    print(json.dumps(dict(players=len(result['players']),errors=len(result['errors']))))
