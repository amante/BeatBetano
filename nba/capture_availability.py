"""Create-only availability sidecar for a fixed NBA fixture cohort.

Collection is a new observation, never a rewrite of a frozen statistical
snapshot. Unknown/uncertain states block a complete active roster.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from sporting_feed import collect as collect_sporting
from espn_current_roster_feed import collect as collect_rosters
from lineup_live_collector import collect as collect_lineups
from player_status_intake import reconcile
from active_roster_resolver import resolve
from joint_minutes_report import stamp
from reproducible_slate import digest
from official_injury_pdf import retrieve as retrieve_official_injury_report


def observe_rotation(snapshot, history, availability):
    from player_game_history import collect
    from rotation_efficiency_report import build

    teams = {g[side] for g in snapshot['predictions'] for side in ('home_team','away_team')}
    historical = sorted((g for g in history if stamp(g['tipoff_utc']) < stamp(snapshot['created_at_utc'])),
                        key=lambda g: stamp(g['tipoff_utc']), reverse=True)
    selected = {}
    for team in sorted(teams):
        recent = [g for g in historical if team in (g['home_team'],g['away_team'])][:5]
        selected.update((str(g['game_id']),g) for g in recent)
    with ThreadPoolExecutor(max_workers=8) as pool:
        samples = list(pool.map(lambda game: collect([game]), selected.values()))
    observed = datetime.now(timezone.utc).isoformat()
    sample = {'players':[p for s in samples for p in s['players']],
              'unavailable_games':[e for s in samples for e in s['unavailable_games']],
              'games_requested':len(selected),
              'source':samples[0]['source'] if samples else None}
    eligible = [g for g in snapshot['predictions'] if stamp(g['tipoff_utc']) > stamp(observed)]
    rotation = build({**snapshot,'predictions':eligible,'created_at_utc':observed},
                     list(selected.values()),sample)
    rotation['observed_at_utc'] = observed
    for gid,game in rotation['games'].items():
        for team,row in game['teams'].items():
            current = availability['games'].get(gid,{}).get('teams',{}).get(team,{})
            ids = {p['player_id'] for p in current.get('players',[])}
            row['current_roster_minutes_coverage'] = sum(
                p['player_id'] in ids and p['minutes_projection'] is not None
                for p in row['provisional_rotation'])
    return rotation,sample


def capture(snapshot,output,history=None):
    if digest({k:v for k,v in snapshot.items() if k!="content_sha256"})!=snapshot.get("content_sha256"):
        raise ValueError("Statistical snapshot hash mismatch")
    now=datetime.now(timezone.utc)
    if not snapshot.get('predictions') or any(not stamp(g.get('tipoff_utc')) or stamp(g['tipoff_utc'])<=now for g in snapshot['predictions']):
        raise ValueError('Entire fixture cohort must still be pregame; no backdating')
    directory=Path(output)
    directory.mkdir(parents=True,exist_ok=False)
    files={}
    def save(name,data):
        raw=json.dumps(data,indent=2,allow_nan=False).encode()
        with (directory/name).open('xb') as f:f.write(raw)
        files[name]=hashlib.sha256(raw).hexdigest()
    errors={}
    def attempt(name,fn,default):
        try:result=fn(snapshot)
        except Exception as exc:
            errors[name]={'error_type':type(exc).__name__,'detail':str(exc)[:1000]}
            result=default
        return result
    sporting=attempt('sporting',collect_sporting,{'games':{}})
    roster=attempt('roster',collect_rosters,{'snapshot_sha256':snapshot['content_sha256'],'games':{}})
    lineups_result=attempt('lineups',collect_lineups,({'snapshot_sha256':snapshot['content_sha256'],'games':{}},{'candidates':[]}))
    lineups,candidates=lineups_result
    official=attempt('official_injury_report',retrieve_official_injury_report,{
        'source_index':'https://official.nba.com/nba-injury-report-2026-27-season/',
        'official_document_retrieved':False,'individual_player_status_verified':False,
        'structured_player_rows':[],'team_report_statuses':[],'raw_page_text':[]})
    # Membership data is stamped after the roster requests finish, rather than
    # declaring all responses observed at the beginning of a network batch.
    roster_completed=datetime.now(timezone.utc).isoformat()
    for game in roster.get('games',{}).values():
        for team in game.get('teams',{}).values():
            if team.get('observed_at_utc'):team['observed_at_utc']=roster_completed
    status=reconcile(snapshot,roster,sporting,official)
    availability=resolve(snapshot,roster,status,lineups)
    for name,obj in [('sporting',sporting),('roster',roster),('lineups',lineups),('lineup_candidates',candidates),('official_injury_source',official),('status',status),('availability',availability)]:save(name+'.json',obj)
    teams=[t for g in availability['games'].values() for t in g['teams'].values()]
    summary={'captured_at_utc':datetime.now(timezone.utc).isoformat(),
        'statistical_snapshot_sha256':snapshot['content_sha256'],
        'statistical_snapshot_created_at_utc':snapshot['created_at_utc'],
        'later_sidecar_not_retroactive_snapshot_update':True,
        'games':len(snapshot['predictions']),'teams':len(teams),
        'roster_members':sum(len(t['players']) for t in teams),
        'matched_injury_claims':sum(len(t) for g in status['games'].values() for t in g['teams'].values()),
        'unmatched_claims':status['unmatched_claims'],'conflicts':status['conflicts'],
        'official_injury_report_retrieved':official.get('official_document_retrieved') is True,
        'official_injury_report_url':official.get('report_url'),
        'official_injury_report_as_of_utc':official.get('source_report_as_of_utc'),
        'official_status_claims_matched':status.get('official_matched_claims',0),
        'official_status_claims_unmatched':len(status.get('official_unmatched_claims',[])),
        'official_injury_status_verification_scope':'matched_reported_players_only; unlisted players remain unknown',
        'official_team_reports_not_submitted':status.get('official_team_reports_not_submitted',[]),
        'known_out':sum(p['status']=='out' for t in teams for p in t['players']),
        'uncertain':sum(p['status']=='questionable' for t in teams for p in t['players']),
        'unknown':sum(p['status']=='unknown' for t in teams for p in t['players']),
        'teams_allocation_ready':sum(t['allocation_ready'] for t in teams),
        'teams_with_provider_lineups':sum(bool(t.get('starters')) for g in lineups['games'].values() for t in g['teams'].values()),
        'no_odds_input':True,'official_injury_status_verified':status.get('official_matched_claims',0)>0,
        'probability_adjustment_authorized':False,'errors':errors}
    if history is not None:
        rotation_result = attempt('rotation',lambda _: observe_rotation(snapshot,history,availability),None)
        if rotation_result is not None:
            rotation, sample = rotation_result
            save('rotation.json',rotation)
            save('player_history.json',sample)
            summary['historical_rotation'] = {
                'observed_at_utc':rotation['observed_at_utc'],
                'games_requested':sample['games_requested'],
                'games_unavailable':len(sample['unavailable_games']),
                'fixtures_covered':len(rotation['games']),
                'roster_player_fixture_estimates':sum(
                    t['current_roster_minutes_coverage'] for g in rotation['games'].values()
                    for t in g['teams'].values())}
    save('summary.json',summary)
    save('manifest.json',{'files':dict(files),'created_at_utc':summary['captured_at_utc']})
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--history')
    args=parser.parse_args()
    print(json.dumps(capture(json.loads(Path(args.snapshot).read_text()),args.output_dir,
                     json.loads(Path(args.history).read_text()) if args.history else None),indent=2))

if __name__=='__main__':main()
