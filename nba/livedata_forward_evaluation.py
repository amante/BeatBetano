"""Score immutable pregame LiveData ML and hybrid pairs against the NBA results ledger."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from official_injury_table import TEAMS
from postmortem_backtest import metrics
from postmortem_engine import save_new, verify_seal
from prospective import utc
from team_identity import canonical

VERSION = 'NBA_LIVEDATA_TEAM_ML_RESEARCH_V1'


def evaluate(reports, results, as_of):
    eligible, candidates, errors = set(), {}, []
    outcomes = {str(row['id']): row for row in results
                if row['sport'] == 'nba' and row['completed'] is True and row['status'] == 'STATUS_FINAL'}
    for report in sorted(reports, key=lambda r: (utc(r['emitted_at_utc']), r['content_sha256'])):
        verify_seal(report)
        emitted = utc(report['emitted_at_utc'])
        if report['model_version'] != VERSION or emitted > utc(as_of):
            raise ValueError('Unexpected research model version or future emission')
        for row in report['games']:
            gid = str(row['game_id'])
            if emitted >= utc(row['tipoff_utc']):
                continue
            eligible.add(gid)
            if row['status'] == 'research_team_ml' and gid not in candidates:
                probabilities = (row['base_home_ml'], row['home_ml'])
                if any(type(p) not in (int, float) or not 0 <= p <= 1 for p in probabilities):
                    raise ValueError('Invalid paired probabilities')
                candidates[gid] = (row, report)
    scored = []
    pending = 0
    for gid, (row, report) in candidates.items():
        result = outcomes.get(gid)
        if result is None:
            pending += 1
            continue
        try:
            if (utc(result['start_utc']) != utc(row['tipoff_utc'])
                    or utc(result['start_utc']) >= utc(as_of)
                    or any(canonical(TEAMS.get(result[side], result[side])) != row[f'{side}_team']
                           for side in ('home', 'away'))):
                raise ValueError('Result fixture identity mismatch')
            home, away = int(result['home_score']), int(result['away_score'])
            if min(home, away) < 0 or home == away:
                raise ValueError('Invalid final score')
        except (KeyError, ValueError, TypeError) as exc:
            errors.append({'game_id': gid, 'reason': str(exc)})
            continue
        scored.append({'game_id': gid, 'outcome_home': int(home > away),
                       'hybrid_home': row['base_home_ml'], 'livedata_home': row['home_ml'],
                       'emitted_at_utc': report['emitted_at_utc'],
                       'research_sha256': report['content_sha256']})
    scores = {name: metrics([(row[f'{name}_home'], row['outcome_home']) for row in scored])
              for name in ('hybrid', 'livedata')}
    return {'as_of_utc': as_of, 'model_version': VERSION, 'selection': 'first_pregame_candidate_per_game',
            'observed_fixtures': len(eligible), 'candidate_fixtures': len(candidates),
            'pending_results': pending, 'result_errors': errors, 'scored_games': scored, 'metrics': scores,
            'delta_livedata_minus_hybrid': {
                key: scores['livedata'][key] - scores['hybrid'][key] if scored else None
                for key in ('brier', 'log_loss')}}


def main():
    parser = argparse.ArgumentParser()
    for name in ('workdir', 'archive', 'outcomes', 'summary'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.archive.mkdir(parents=True, exist_ok=True)
    for source in sorted(args.workdir.glob('nba-*.team-metrics/team_ml_research.json')):
        report = json.loads(source.read_text())
        verify_seal(report)
        target = args.archive / (report['content_sha256'] + '.json')
        if not target.exists():
            save_new(target, report)
    reports = [json.loads(path.read_text()) for path in sorted(args.archive.glob('*.json'))]
    summary = evaluate(reports, json.loads(args.outcomes.read_text()), datetime.now(timezone.utc).isoformat())
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps({key: summary[key] for key in ('observed_fixtures', 'candidate_fixtures',
                                                   'pending_results', 'delta_livedata_minus_hybrid')}))


if __name__ == '__main__':
    main()
