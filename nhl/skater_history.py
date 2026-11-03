"""Prior-day official skater game logs; observed counts, no probability effect."""
from datetime import date

def summarize(player_id, payload, cutoff_day):
    cutoff=date.fromisoformat(cutoff_day)
    if type(player_id) is not int or player_id<=0:raise ValueError('Invalid player ID')
    rows=payload.get('gameLog')
    if not isinstance(rows,list):raise ValueError('Missing game log')
    seen=set();goals=shots=seconds=games=0
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
        goals+=g;shots+=s;seconds+=minutes*60+secs;games+=1
    return dict(player_id=player_id,role='skater',skater_games=games,skater_goals=goals,skater_shots=shots,toi_games=games,toi_seconds=seconds,cutoff_exclusive=cutoff_day,applied_to_probability=False)

def collect(report,rosters,fetcher=None):
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
    season=season_for(at.date().isoformat());cutoff=at.date().isoformat()
    def one(item):
        pid,clubs=item
        try:
            payload,source=fetcher(pid,season)
            stamp=parse_utc(source['retrieved_at'])
            if stamp<at or any(stamp>=starts[t] for t in clubs):raise ValueError('Source outside pregame capture window')
            if source['url']!=f'https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2':raise ValueError('Unexpected history source')
            return str(pid),dict(summarize(pid,payload,cutoff),source=source,roster_teams=sorted(clubs)),payload,None
        except (OSError,ValueError,KeyError,TypeError) as e:return str(pid),None,None,str(e)[:160]
    with ThreadPoolExecutor(max_workers=4) as executor:rows=list(executor.map(one,pool.items()))
    return dict(kind='nhl_skater_history_capture_v1',source_capture_as_of=report['generated_at_utc'],season=season,cutoff_exclusive=cutoff,players={pid:r for pid,r,_,e in rows if e is None},errors={pid:e for pid,_,_,e in rows if e is not None},missing_roster_teams=sorted(teams-seen),applied_to_probability=False,limitations=['Roster identity is not an expected lineup.','Historical TOI is not expected deployment.','Independent baseline lineup and fitted player effects remain required.']),{pid:p for pid,_,p,e in rows if e is None}

if __name__=='__main__':
    import argparse,gzip,json
    from pathlib import Path
    p=argparse.ArgumentParser()
    for name in ('report','rosters','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();result,raw=collect(json.loads(Path(a.report).read_text()),json.loads(Path(a.rosters).read_text()))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));out.with_suffix('.sources.json.gz').write_bytes(gzip.compress(json.dumps(raw).encode(),mtime=0))
    print(json.dumps(dict(players=len(result['players']),errors=len(result['errors']))))
