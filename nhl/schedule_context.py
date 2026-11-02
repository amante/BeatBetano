"""Official schedule context: start-to-start gap, B2B and venue changes, not inferred travel."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
from nhl.pulso_goalie_multisource_257 import TEAM_NAMES
from nhl.pulso_goalie_history_251 import season_for
from nhl.pulso_pregame_v7 import parse_utc
from nhl.special_teams_capture import fetch


def team_context(team,payload,fixture,source_at):
    if not isinstance(payload.get('games'),list):raise ValueError('Missing official schedule')
    games={str(g['id']):g for g in payload['games']}
    if len(games)!=len(payload['games']):raise ValueError('Duplicate schedule game')
    game=games.get(str(fixture['game_id']));start=parse_utc(fixture['start_utc']);at=parse_utc(source_at)
    if at>=start:raise ValueError('Game already started at source retrieval')
    if game is None or game['homeTeam']['abbrev']!=fixture['home'] or game['awayTeam']['abbrev']!=fixture['away'] or parse_utc(game['startTimeUTC'])!=start:raise ValueError('Official fixture identity changed')
    previous=[g for g in games.values() if team in (g.get('homeTeam',{}).get('abbrev'),g.get('awayTeam',{}).get('abbrev')) and parse_utc(g['startTimeUTC'])<start and g.get('gameScheduleState') not in ('PPD','CNCL')]
    if not previous:return dict(status='missing_previous_fixture',previous_game_id=None,hours_between_starts=None,back_to_back=None,venue_changed=None,travel_km=None,applied_to_probability=False)
    prior=max(previous,key=lambda g:parse_utc(g['startTimeUTC']))
    prior_start=parse_utc(prior['startTimeUTC']);old=prior.get('venue',{}).get('default');current=game.get('venue',{}).get('default')
    completed=prior.get('gameState') in ('OFF','FINAL') and prior_start<at
    return dict(status='observed_schedule_context' if completed else 'planned_previous_fixture_not_completed',previous_game_id=str(prior['id']),previous_start_utc=prior['startTimeUTC'],previous_game_state=prior.get('gameState'),hours_between_starts=(start-prior_start).total_seconds()/3600,back_to_back=(date.fromisoformat(game['gameDate'])-date.fromisoformat(prior['gameDate'])).days==1 if game.get('gameDate') and prior.get('gameDate') else None,previous_venue=old,venue=current,venue_changed=old!=current if old and current else None,travel_km=None,actual_rest_hours=None,applied_to_probability=False)


def collect(report,get=fetch):
    if report.get('data_kind')!='source_readiness_only' or report.get('official_predictions')!=0:raise ValueError('NHL source report required')
    capture=parse_utc(report['generated_at_utc']);season=season_for(capture.date().isoformat())
    teams=sorted({t for f in report['games'] for t in (f['home'],f['away'])})
    if any(t not in TEAM_NAMES for t in teams):raise ValueError('Unknown NHL team')
    def retrieve(team):
        url='https://api-web.nhle.com/v1/club-schedule-season/'+team+'/'+season
        try:
            raw,at=get(url)
            if parse_utc(at)<capture:raise ValueError('Schedule source predates requested capture')
            return team,json.loads(raw),dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),retrieved_at=at),raw.decode(),None
        except (OSError,ValueError,TypeError,KeyError) as e:return team,None,None,None,str(e)[:160]
    with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(retrieve,teams))
    cache={t:(p,m) for t,p,m,_,e in responses if e is None};archive={t:raw for t,_,_,raw,e in responses if e is None};errors={t:e for t,_,_,_,e in responses if e is not None}
    games=[]
    for f in report['games']:
        sides={}
        for team in (f['home'],f['away']):
            try:
                payload,metadata=cache[team]
                sides[team]=dict(team_context(team,payload,f,metadata['retrieved_at']),source=metadata)
            except (ValueError,KeyError,TypeError) as e:sides[team]=dict(status='missing_or_invalid_source',reason=errors.get(team,str(e)[:160]),applied_to_probability=False)
        games.append(dict(game_id=str(f['game_id']),home=f['home'],away=f['away'],start_utc=f['start_utc'],teams=sides))
    return dict(kind='nhl_official_schedule_context_v1',source_capture_as_of=report['generated_at_utc'],as_of_utc=max([parse_utc(m['retrieved_at']) for _,_,m,_,e in responses if e is None]+[capture]).isoformat(),games=games,errors=errors,probabilities_modified=False,limitations=['Hours are between scheduled starts, not verified rest since the previous final horn.','Venue change is observed; travel distance/route is not inferred.','Planned prior fixtures do not prove actual workload.']),archive


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result,archive=collect(json.loads(Path(a.report).read_text()))
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
    path.with_suffix('.sources.json.gz').write_bytes(gzip.compress(json.dumps(archive).encode(),mtime=0))
    print(json.dumps(dict(fixtures=len(result['games']),observed_sides=sum(t['status']=='observed_schedule_context' for g in result['games'] for t in g['teams'].values()),errors=result['errors'])))
