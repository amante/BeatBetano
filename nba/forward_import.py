"""Adopt an existing immutable pregame snapshot with pretip Git provenance.

This imports original probabilities only. It cannot manufacture a forecast for
an already-started game. A committed source prior to every tipoff is mandatory.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from forward_capture import DEFAULT_PROTOCOL,verify_sources
from forward_ledger import seal,save_new,in_scope,verify_observation
from reproducible_slate import digest
from prospective import utc


def adopt(folder,protocol,committed_at,git_blob):
    verify_sources(protocol)
    folder=Path(folder);snapshot=json.loads((folder/'snapshot.json').read_text())
    if digest({k:v for k,v in snapshot.items() if k!='content_sha256'})!=snapshot['content_sha256']:
        raise ValueError('Imported snapshot digest mismatch')
    manifest=json.loads((folder/'manifest.json').read_text())
    file_hash=hashlib.sha256((folder/'snapshot.json').read_bytes()).hexdigest()
    if manifest['files']['snapshot.json']!=file_hash:raise ValueError('Archive file manifest mismatch')
    if not git_blob or utc(committed_at)<utc(snapshot['created_at_utc']):raise ValueError('Missing or invalid pretip publication proof')
    fixtures={g['game_id']:g for g in json.loads((folder/'fixtures.json').read_text())}
    predictions=[];schedule=[]
    for p in snapshot['predictions']:
        row=fixtures[p['game_id']]
        if not in_scope(row,protocol):continue
        if utc(committed_at)>=utc(p['tipoff_utc']):raise ValueError('Snapshot was not committed before tipoff')
        for key in ('home_team','away_team','tipoff_utc'):
            if p[key]!=row[key]:raise ValueError('Imported fixture identity mismatch')
        predictions.append({k:p[k] for k in ('game_id','home_team','away_team','tipoff_utc','elo_p_home','challenger_p_home')}|
                           {'prediction_as_of_utc':snapshot['created_at_utc']})
        schedule.append({**row,'source_state':'pre','source_status':'archived_pretip',
                         'completed':False,'observed_at_utc':snapshot['created_at_utc']})
    result=seal({'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'run_id':'import-original-nov4','protocol_sha256':digest(protocol),
        'source':'repository_archive_with_pretip_git_provenance','schedule':schedule,
        'predictions':predictions,'source_errors':[],
        'provenance':{'snapshot_content_sha256':snapshot['content_sha256'],'file_sha256':file_hash,
                      'git_blob':git_blob,'committed_at_utc':committed_at},'no_odds_input':True})
    verify_observation(result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',default='reports/nba-2026-11-04')
    p.add_argument('--protocol',default=DEFAULT_PROTOCOL);p.add_argument('--root',default='reports/nba-forward')
    a=p.parse_args();path=str(Path(a.folder)/'snapshot.json')
    committed_raw=subprocess.check_output(['git','log','-1','--format=%cI','--',path],text=True).strip()
    committed=datetime.fromisoformat(committed_raw).astimezone(timezone.utc).isoformat()
    blob=subprocess.check_output(['git','rev-parse','HEAD:'+path],text=True).strip()
    # Ensure the file being imported is the actual version proved by Git.
    actual=subprocess.check_output(['git','show','HEAD:'+path])
    if actual!=Path(path).read_bytes():raise ValueError('Working source differs from committed snapshot')
    obs=adopt(a.folder,json.loads(Path(a.protocol).read_text()),committed,blob)
    save_new(Path(a.root)/'observations'/'import-original-nov4.json',obs)
    print(json.dumps({'imported_original_pregame_pairs':len(obs['predictions']),'provenance':obs['provenance']},indent=2))

if __name__=='__main__':main()
