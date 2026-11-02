"""Dated official PP/PK counts with a verified completed source day; no fitted ML effect."""
import argparse
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from nhl.pulso_goalie_multisource_257 import TEAM_NAMES,norm
from nhl.pulso_pregame_v7 import parse_utc
from nhl.pulso_goalie_history_251 import season_for

API='https://api.nhle.com/stats/rest/en/team/'


def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'PULSO-special-teams/1.0'}),timeout=25) as response:raw=response.read(4_000_001)
    if len(raw)>4_000_000:raise ValueError('Oversized NHL response')
    return raw,datetime.now(timezone.utc).isoformat()


def urls(day,season):
    query=urlencode(dict(isAggregate='false',isGame='false',start=0,limit=100,cayenneExp='seasonId='+season+' and gameTypeId=2 and gameDate<="'+day+'"'))
    return {key:API+part+'?'+query for key,part in [('pp','powerplay'),('pk','penaltykill')]}


def parse_counts(pp,pk,season):
    index={norm(name):team for team,name in TEAM_NAMES.items()};result={};unmatched=[]
    for key,data in [('pp',pp),('pk',pk)]:
        rows=data.get('data')
        if not isinstance(rows,list) or data.get('total')!=len(rows) or len(rows)>100:raise ValueError('Incomplete official special-teams response')
        seen=set()
        for r in rows:
            if str(r.get('seasonId'))!=season:raise ValueError('Wrong statistics season')
            team=index.get(norm(r.get('teamFullName','')))
            if team is None:unmatched.append(r.get('teamFullName'));continue
            if team in seen:raise ValueError('Duplicate team statistics')
            seen.add(team)
            goals,trials=(r.get('powerPlayGoalsFor'),r.get('ppOpportunities')) if key=='pp' else (r.get('ppGoalsAgainst'),r.get('timesShorthanded'))
            n=r.get('gamesPlayed')
            if any(type(v) is not int for v in (goals,trials,n)) or not 0<=goals<=trials or n<0:raise ValueError('Invalid observed counts')
            record=result.setdefault(team,{})
            if record.get('games_played',n)!=n:raise ValueError('PP and PK game counts disagree')
            record['games_played']=n
            if key=='pp':record.update(powerplay_goals=goals,powerplay_opportunities=trials)
            else:record.update(opponent_powerplay_goals=goals,times_shorthanded=trials)
    return result,unmatched


def collect(report,get=fetch):
    if report.get('data_kind')!='source_readiness_only' or report.get('official_predictions')!=0:raise ValueError('NHL source report required')
    capture=parse_utc(report['generated_at_utc'])
    day=(capture.date()-timedelta(days=1)).isoformat();season=season_for(capture.date().isoformat())
    score_url='https://api-web.nhle.com/v1/score/'+day
    raw,at=get(score_url);score=json.loads(raw)
    if score.get('currentDate')!=day or not isinstance(score.get('games'),list):raise ValueError('Invalid official cutoff-day scoreboard')
    if any(g.get('gameState') not in ('OFF','FINAL') and g.get('gameScheduleState') not in ('PPD','CNCL') for g in score['games']):raise ValueError('Cutoff day still has unfinished games')
    archive={'score':raw.decode()};sources=[dict(url=score_url,sha256=hashlib.sha256(raw).hexdigest(),retrieved_at=at)];payloads={}
    for key,url in urls(day,season).items():
        raw,at=get(url);payloads[key]=json.loads(raw);archive[key]=raw.decode();sources.append(dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),retrieved_at=at))
    asof=max(parse_utc(s['retrieved_at']) for s in sources)
    if any(parse_utc(s['retrieved_at'])<capture for s in sources):raise ValueError('Source timestamp predates capture request')
    counts,unmatched=parse_counts(payloads['pp'],payloads['pk'],season)
    selected={};errors=[]
    for team in sorted({t for g in report['games'] for t in (g['home'],g['away'])}):
        value=counts.get(team,{})
        if not all(k in value for k in ('powerplay_goals','powerplay_opportunities','opponent_powerplay_goals','times_shorthanded')):
            errors.append(dict(team=team,reason='missing_complete_special_teams_counts'));continue
        selected[team]=value
    result=dict(kind='nhl_dated_special_teams_counts_v1',as_of_utc=asof.isoformat(),source_capture_as_of=report['generated_at_utc'],effective_day=day,season=season,cutoff_day_completed=True,teams=selected,sources=sources,errors=errors,unmatched_source_teams=unmatched,probabilities_modified=False)
    return result,archive


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=json.loads(Path(a.report).read_text())
    try:result,archive=collect(report)
    except (OSError,ValueError,KeyError,TypeError) as e:
        result=dict(kind='nhl_dated_special_teams_counts_v1',teams={},errors=[dict(reason='source_unavailable_or_invalid',detail=str(e)[:180])],probabilities_modified=False);archive={}
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
    path.with_suffix('.sources.json.gz').write_bytes(gzip.compress(json.dumps(archive).encode(),mtime=0))
    print(json.dumps(dict(teams=len(result['teams']),errors=result['errors'])))
