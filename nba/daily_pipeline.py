"""End-to-end NBA pregame execution with independently verified historical ledger.

Fetches live fixtures and generates an immutable three-model snapshot. Historical
game data must be supplied and inspected separately; never fabricate team ratings.
"""
import subprocess
import sys
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisport.daily_forecasts import publish
from current_feed import fetch_day
from prospective import generate

def run(history,scoreboard,created_at):
    fixtures=scoreboard["future_fixtures"]
    if not fixtures:
        raise ValueError("No not-yet-started NBA regular-season games in scoreboard")
    if "as_of_utc" not in scoreboard:
        raise ValueError("Source snapshot timestamp missing")
    feed_at=datetime.fromisoformat(scoreboard["as_of_utc"].replace("Z","+00:00"))
    snap_at=datetime.fromisoformat(created_at.replace("Z","+00:00"))
    if feed_at.tzinfo is None or snap_at.tzinfo is None or feed_at>snap_at:
        raise ValueError("Invalid scoreboard observation time")
    if (snap_at-feed_at).total_seconds()>300:
        raise ValueError("Scoreboard older than five minutes; refresh before predictions")
    # Preserve the signed-by-digest snapshot body unchanged.
    return generate(history,fixtures,created_at)

def sporting_report(snapshot, evidence=None, boxscores=None, **kwargs):
    """Run the existing two-sided engine and expose its exact integration gaps."""
    from postmortem_engine import build
    evidence = evidence if evidence is not None else {"snapshot_sha256":snapshot["content_sha256"],"games":{}}
    report = build(snapshot, evidence, boxscores if boxscores is not None else {"games":[]}, **kwargs)
    report_summary = {"baseline_snapshot_sha256":snapshot["content_sha256"], "games":len(report['games']),
        "integrated_research_games":sum(g['challenger'] is not None for g in report['games']),
        "game_diagnostics":[{"game_id":g['game_id'], "missing":g['missing'],
                             "lineup_context":g.get('lineup_context',{})} for g in report['games']],
        "calibrated":report['calibrated'], "production_approved":report['production_approved']}
    return report, report_summary


def observe_availability(snapshot_path, snapshot, history_path=None):
    """Collect a later observation with a time budget independent of the baseline."""
    folder = snapshot_path.with_suffix('.availability')
    command = [sys.executable, str(Path(__file__).with_name('capture_availability.py').resolve()),
               '--snapshot', str(snapshot_path), '--output-dir', str(folder)]
    if history_path is not None:
        command += ['--history', str(history_path)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=75)
        if completed.returncode:
            return {'status':'source_error', 'detail':completed.stderr[-600:]}
        summary = json.loads((folder/'summary.json').read_text())
        if summary['statistical_snapshot_sha256'] != snapshot['content_sha256']:
            raise ValueError('Availability observation belongs to another snapshot')
        return {'status':'captured', **summary}
    except subprocess.TimeoutExpired:
        return {'status':'source_timeout'}
    except (OSError, ValueError, KeyError) as exc:
        return {'status':'source_error', 'detail':str(exc)[:600]}


def observe_team_metrics(snapshot_path, history_path, day):
    folder = snapshot_path.with_suffix('.team-metrics')
    script = Path(__file__).with_name('livedata_team_metrics.py').resolve()
    command = [sys.executable, str(script), '--date', day, '--snapshot', str(snapshot_path),
               '--history', str(history_path), '--output-dir', str(folder)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
        path = folder / 'team_metrics.json'
        if not path.exists():
            return {'status': 'source_error', 'detail': completed.stderr[-600:]}
        report = json.loads(path.read_text())
        return {'status': report['selected_source'], 'cutoff_date': report['cutoff_date'],
                'official_teams': len(report['official']['teams']),
                'fallback_games': len(report.get('fallback', {}).get('games', [])),
                'fallback_errors': len(report.get('fallback', {}).get('errors', [])),
                'crosswalk': report.get('crosswalk')}
    except subprocess.TimeoutExpired:
        return {'status': 'source_timeout'}
    except (OSError, ValueError, KeyError) as exc:
        return {'status': 'source_error', 'detail': str(exc)[:600]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True,help="Validated completed-game ledger JSON")
    p.add_argument("--date",required=True,help="NBA scoreboard date YYYY-MM-DD")
    p.add_argument("--output",required=True,help="Create-only immutable JSON snapshot")
    p.add_argument('--allow-empty',action='store_true',help='Record zero eligible games without error')
    p.add_argument('--postmortem-evidence',help='Verified two-sided player/possession features JSON')
    p.add_argument('--postmortem-boxscores',help='Paired historical boxscore archive JSON')
    p.add_argument('--forecast-archive',help='Persistent per-event forecast revision directory')
    p.add_argument('--capture-availability',action='store_true',help='Collect a separate pregame roster and injury observation')
    p.add_argument('--capture-team-metrics',action='store_true')
    x=p.parse_args()
    now=datetime.now(timezone.utc).isoformat()
    scoreboard=fetch_day(x.date,now)
    history=json.loads(Path(x.history).read_text())
    if x.allow_empty and not scoreboard["future_fixtures"]:
        target=Path(x.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        status={"date":x.date,"as_of_utc":scoreboard["as_of_utc"],
                "status":"no_eligible_pregame_games",
                "future_fixtures":0,"completed_games":len(scoreboard["completed_games"]),
                "snapshot_created":False,
                "note":"No pregame fixtures remain; no probabilities were generated."}
        (target.parent/"pregame_status.json").write_text(json.dumps(status,indent=2))
        print(json.dumps(status,indent=2))
        return
    snapshot=run(history,scoreboard,now)
    target=Path(x.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as f:json.dump(snapshot,f,indent=2)
    publication=publish('nba',snapshot,x.forecast_archive or target.parent/'forecast_archive',revision='nba-existing-baselines',live_only=True)
    target.with_name(target.stem+'.forecasts.json').write_text(json.dumps(publication,indent=2))
    from postmortem_engine import save_new
    # Preserve the baseline bytes and seal a separate complete sporting snapshot.
    evidence = (json.loads(Path(x.postmortem_evidence).read_text()) if x.postmortem_evidence else
                {"snapshot_sha256":snapshot["content_sha256"],"games":{}})
    boxscores = json.loads(Path(x.postmortem_boxscores).read_text()) if x.postmortem_boxscores else {"games":[]}
    sporting, integration = sporting_report(snapshot,evidence,boxscores)
    save_new(target.with_name(target.stem+".postmortem.json"),sporting)
    if x.capture_availability:
        integration['availability_observation'] = observe_availability(target, snapshot, x.history)
    if x.capture_team_metrics:
        integration["team_metrics_observation"] = observe_team_metrics(target, x.history, x.date)
    with target.with_name(target.stem+".integration.json").open("x") as f:
        json.dump(integration,f,indent=2)
    print(json.dumps({"date":x.date,"games":len(snapshot["predictions"]),
        "created_at_utc":snapshot["created_at_utc"],
        "status":"snapshot_created; candidate predictions not calibrated",
        "output":str(target), "sporting_integration":integration},indent=2))
if __name__=="__main__":main()
