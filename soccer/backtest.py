"""Fixed chronological protocol; validation selects regularization, never holdout."""
import argparse
import json
from pathlib import Path
from .data import load_history
from .poisson import fit, predict, frequency, metrics


def evaluate(directory):
    rows, manifest = load_history(directory)
    seasons = ['2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
    if [m['season'] for m in manifest] != seasons: raise ValueError('Expected five specified complete seasons')
    train = [r for r in rows if r['season'] in seasons[:2]]
    validation = [r for r in rows if r['season'] == seasons[2]]
    grid = []
    for penalty in (.001, .01, .1):
        model = fit(train, penalty)
        score = metrics([predict(model, r['home'], r['away'], r['date'])['probabilities'] for r in validation], validation)
        grid.append(dict(penalty=penalty, **score))
    chosen = min(grid, key=lambda r: r['log_loss'])['penalty']
    evaluations, frozen = [], []
    for season in seasons[3:]:
        prior = [r for r in rows if r['season'] < season]
        test = [r for r in rows if r['season'] == season]
        model, baseline = fit(prior, chosen), frequency(prior)
        forecasts = [dict(id=r['id'], date=r['date'], **predict(model, r['home'], r['away'], r['date'])) for r in test]
        frozen.extend(forecasts)
        evaluations.append(dict(season=season, trained_through=model['trained_through'], poisson=metrics([p['probabilities'] for p in forecasts], test), frequency=metrics([baseline]*len(test), test), unknown_team_games=sum(bool(p['unknown_teams']) for p in forecasts)))
    return dict(status='research_only', live_parameters_changed=False, source_manifest=manifest, protocol='Season-frozen expanding training; validation 2023-24 selects log-loss penalty; holdouts 2024-25 and 2025-26 never select parameters. Retrospective reconstruction, not genuinely pregame-captured evidence.', markets=['home_90', 'draw_90', 'away_90'], brier_definition='Mean across fixtures of SUM over three classes of squared probability errors', validation_grid=grid, selected_penalty=chosen, holdouts=evaluations, forecasts=frozen)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = evaluate(args.history)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2)+'\n')
