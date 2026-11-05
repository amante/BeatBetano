"""Publish the accumulated forward cohort and attributed sporting coverage."""
import argparse
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from forward_ledger import load_observations,reconstruct
from forward_capture import DEFAULT_PROTOCOL,verify_sources
from sporting_archive import bundles,team_observation
from prospective import utc


def build(protocol,observations,records,as_of,evidence_errors=None):
    ledger=reconstruct(observations,protocol,as_of)
    rows=[]
    for g in ledger['games']:
        teams={t:team_observation(records,g['game_id'],t,g['tipoff_utc'],as_of) for t in (g['home_team'],g['away_team'])}
        rows.append({**g,'sporting':teams,'sporting_adjustment_applied':False,'plus20_home':None,'plus20_away':None})
    coverage={}
    for obs in sorted(observations,key=lambda o:utc(o['created_at_utc'])):
        if utc(obs['created_at_utc'])>utc(as_of):continue
        for day in obs.get('source_day_coverage',[]):coverage[day['league_date']]=day['observed_at_utc']
        for err in obs.get('source_errors',[]):
            if err.get('league_date'):coverage.pop(err['league_date'],None)
    # A Chile date can overlap two US league dates. Never call an uncovered
    # future day empty just because there are no rows in the current packet.
    chile=ZoneInfo('America/Santiago');ny=ZoneInfo('America/New_York')
    day=utc(protocol['forecast_window_start_utc']).astimezone(chile).date()
    last=utc(protocol['forecast_window_end_exclusive_utc']).astimezone(chile).date()
    calendar={}
    while day<=last:
        start=datetime.combine(day,datetime.min.time(),tzinfo=chile)
        dates={start.astimezone(ny).date().isoformat(),(start+timedelta(days=1,microseconds=-1)).astimezone(ny).date().isoformat()}
        calendar[day.isoformat()]=all(d in coverage for d in dates)
        day+=timedelta(days=1)
    return {'kind':'nba_forward_publication_v2','as_of_utc':as_of,'protocol_sha256':ledger['protocol_sha256'],
            'last_source_capture_utc':max((o['created_at_utc'] for o in observations if utc(o['created_at_utc'])<=utc(as_of)),key=utc,default=None),
            'games':rows,'calendar_date_coverage_chile':calendar,
            'source_error_count':len(ledger['source_errors']),'sporting_evidence_errors':evidence_errors or [],
            'performance_metrics':None,'evaluation_status':ledger['performance_evaluation_status'],
            'calibrated':False,'sporting_adjustment_applied':False,'no_odds_input':True,
            'scope_excludes_knicks':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',default=DEFAULT_PROTOCOL)
    p.add_argument('--ledger-root',default='reports/nba-forward');p.add_argument('--sporting-root',default='reports/nba-sporting')
    p.add_argument('--output',default='frontend/data/nba-forward-latest.json');a=p.parse_args()
    protocol=json.loads(Path(a.protocol).read_text());verify_sources(protocol)
    if datetime.now(timezone.utc)>=utc(protocol['forecast_window_end_exclusive_utc'])+timedelta(days=14) and Path(a.output).exists():
        print('Collection window closed; retaining final published packet');return
    records,errors=bundles(a.sporting_root)
    r=build(protocol,load_observations(a.ledger_root),records,datetime.now(timezone.utc).isoformat(),errors)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(r,indent=2,allow_nan=False))
    print(json.dumps({'games':len(r['games']),'source_capture':r['last_source_capture_utc'],'sporting_errors':len(errors)}))

if __name__=='__main__':main()
