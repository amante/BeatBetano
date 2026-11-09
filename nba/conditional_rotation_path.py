"""Isolate the effect of a conditional minute change on the existing score path."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from possession_path_features import extract
from postmortem_engine import PARAMETERS, matchup_path, provenance, save_new, verify_seal
from prospective import utc
from reproducible_slate import digest
from score_path import number


def build(snapshot, scenario, coverage, team_ml, archive, emitted_at, simulations=4000):
    for report in (snapshot, scenario, coverage, team_ml):
        verify_seal(report)
    baseline = snapshot['content_sha256']
    if any(r['baseline_snapshot_sha256'] != baseline for r in (scenario, coverage, team_ml)):
        raise ValueError('Research inputs belong to different baselines')
    archive_sha = digest(archive)
    if (scenario['coverage_sha256'] != coverage['content_sha256']
            or coverage['effects']['input_sha256'] != archive_sha
            or scenario.get('usage_archive_sha256') != archive_sha):
        raise ValueError('Scenario, usage and player effects must share the possession sample')
    fixture = next(g for g in snapshot['predictions'] if str(g['game_id']) == scenario['game_id'])
    cutoff, tip = utc(emitted_at), utc(fixture['tipoff_utc'])
    if not max(utc(r['emitted_at_utc']) for r in (scenario, coverage, team_ml)) <= cutoff < tip:
        raise ValueError('Forecast must follow its evidence and precede tipoff')
    provenance(archive['evidence'], cutoff, tip, 'possession archive')
    paths = extract(archive, emitted_at, fixture['tipoff_utc'])['teams']
    ratings = team_ml['ratings']
    zero = {'offense_delta_per_100': 0.0, 'defense_delta_per_100': 0.0,
            'turnover_rate_delta': 0.0, 'forced_turnover_rate_delta': 0.0}
    reference, adjusted, blocked = {}, {}, {}
    for team in (fixture['home_team'], fixture['away_team']):
        reasons = []
        changes = scenario['teams'][team]['minute_changes']
        if not changes:
            reasons.append('missing_minute_allocation')
        if scenario['teams'][team].get('usage', {}).get('status') != 'complete_sample':
            reasons.append('incomplete_usage_sample')
        if paths.get(team, {}).get('status') != 'research_features_only':
            reasons.append(paths.get(team, {}).get('status', 'missing_path_features'))
        if ratings.get(team, {}).get('status') != 'descriptive_schedule_adjusted':
            reasons.append('insufficient_opponent_adjusted_ratings')
        reference[team] = dict(zero)
        adjusted[team] = dict(zero)
        for row in changes:
            delta = row['minute_delta']
            if not delta:
                continue
            effect = coverage['effects']['players'].get(row['nba_player_id'], {})
            if not row['effect_supported'] or effect.get('status') != 'research_effects_only':
                reasons.append('unsupported_player_effect:' + row['espn_player_id'])
                continue
            sample = number(effect['effect_sample_possessions'], 1, 1000000, 'effect sample')
            weight = delta / 48 * sample / (sample + PARAMETERS['on_off_prior_possessions'])
            for side in ('offense', 'defense'):
                adjusted[team][side + '_delta_per_100'] += weight * number(
                    effect[side + '_effect_per_100'], -30, 30, side + ' player effect')
        if reasons:
            blocked[team] = reasons
    paths_output = None
    if not blocked:
        try:
            seed = 2026271
            base = matchup_path(fixture, paths, ratings, reference, simulations, seed)
            update = matchup_path(fixture, paths, ratings, adjusted, simulations, seed)
            before, after = (r['path']['probabilities'] for r in (base, update))
            paths_output = {'reference': base, 'conditional': update,
                            'delta': {key: after[key] - before[key] for key in before}}
        except ValueError as exc:
            blocked['simulation'] = [str(exc)]
    report = {'game_id': str(fixture['game_id']), 'emitted_at_utc': emitted_at,
              'tipoff_utc': fixture['tipoff_utc'], 'home_team': fixture['home_team'],
              'away_team': fixture['away_team'], 'model_version': 'NBA_CONDITIONAL_ROTATION_PATH_V1',
              'baseline_snapshot_sha256': baseline, 'scenario_sha256': scenario['content_sha256'],
              'coverage_sha256': coverage['content_sha256'], 'team_ml_sha256': team_ml['content_sha256'],
              'possession_sha256': archive_sha, 'status': 'research_scenario' if paths_output else 'PASS',
              'rotation_rating_deltas': adjusted, 'blocked': blocked, 'comparison': paths_output,
              'assumptions': ['Conditional minutes and availability from the scenario.',
                              'Turnover pressure and fatigue held fixed across both branches.',
                              'Historical usage is a coverage check and does not alter the rating deltas.'],
              'calibrated': False, 'production_approved': False, 'no_odds_input': True}
    return {**report, 'content_sha256': digest(report)}


def main():
    parser = argparse.ArgumentParser()
    for name in ('snapshot', 'scenario', 'coverage', 'team-ml', 'possessions', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = build(*(json.loads(path.read_text()) for path in
                     (args.snapshot, args.scenario, args.coverage, args.team_ml, args.possessions)),
                   datetime.now(timezone.utc).isoformat())
    save_new(args.output, report)
    print(json.dumps({key: report[key] for key in ('status', 'blocked', 'rotation_rating_deltas')}))


if __name__ == '__main__':
    main()
