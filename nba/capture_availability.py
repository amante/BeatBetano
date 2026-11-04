"""Create-only availability sidecar for a fixed NBA fixture cohort.

Collection is a new observation, never a rewrite of a frozen statistical
snapshot. Unknown/uncertain states block a complete active roster.
"""
import argparse
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


def capture(snapshot,output):
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
    # Membership data is stamped after the roster requests finish, rather than
    # declaring all responses observed at the beginning of a network batch.
    roster_completed=datetime.now(timezone.utc).isoformat()
    for game in roster.get('games',{}).values():
        for team in game.get('teams',{}).values():
            if team.get('observed_at_utc'):team['observed_at_utc']=roster_completed
    status=reconcile(snapshot,roster,sporting)
    availability=resolve(snapshot,roster,status,lineups)
    for name,obj in [('sporting',sporting),('roster',roster),('lineups',lineups),('lineup_candidates',candidates),('status',status),('availability',availability)]:save(name+'.json',obj)
    teams=[t for g in availability['games'].values() for t in g['teams'].values()]
    summary={'captured_at_utc':datetime.now(timezone.utc).isoformat(),
        'statistical_snapshot_sha256':snapshot['content_sha256'],
        'statistical_snapshot_created_at_utc':snapshot['created_at_utc'],
        'later_sidecar_not_retroactive_snapshot_update':True,
        'games':len(snapshot['predictions']),'teams':len(teams),
        'roster_members':sum(len(t['players']) for t in teams),
        'matched_injury_claims':sum(len(t) for g in status['games'].values() for t in g['teams'].values()),
        'unmatched_claims':status['unmatched_claims'],'conflicts':status['conflicts'],
        'known_out':sum(p['status']=='out' for t in teams for p in t['players']),
        'uncertain':sum(p['status']=='questionable' for t in teams for p in t['players']),
        'unknown':sum(p['status']=='unknown' for t in teams for p in t['players']),
        'teams_allocation_ready':sum(t['allocation_ready'] for t in teams),
        'teams_with_provider_lineups':sum(bool(t.get('starters')) for g in lineups['games'].values() for t in g['teams'].values()),
        'no_odds_input':True,'official_injury_status_verified':False,
        'probability_adjustment_authorized':False,'errors':errors}
    save('summary.json',summary)
    save('manifest.json',{'files':dict(files),'created_at_utc':summary['captured_at_utc']})
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    print(json.dumps(capture(json.loads(Path(args.snapshot).read_text()),args.output_dir),indent=2))

if __name__=='__main__':main()
