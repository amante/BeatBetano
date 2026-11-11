# NBA availability impact: temporal walk-forward research

`availability_walk_forward.py` takes a frozen game-level ledger and fits a single ridge-logistic coefficient for absence-conditioned production. For each holdout season it trains only on completed games from earlier seasons, adds the learned coefficient to the frozen baseline log-odds, and compares candidate vs. baseline Brier score, log loss, and accuracy.

The feature is the home-minus-away difference in net points per game after the scenario removes explicitly OUT players and redistributes their minutes to eligible rotation players. The coefficient is learned from earlier outcomes; the script does not assign a hand-written win-probability value to points lost. The frozen baseline and published predictions are never modified.

## Required row fields

Each input row represents one game and must include:

- `game_id`, `season_end_year`, `tipoff_utc`, `prediction_as_of_utc`, `feature_observed_at_utc`;
- `baseline_model_version`, `baseline_p_home`, and binary `home_won`;
- `home_net_output_change_per_game` and `away_net_output_change_per_game` (redistributed output minus output lost, from the official injury impact scenario);
- `features_point_in_time_verified: true`, `both_team_scenarios_complete: true`;
- `source_snapshot_sha256` and `scenario_sha256`.

The feature observation must be no later than the frozen prediction, which must precede tipoff. Duplicate games, incomplete scenarios, missing hashes, future evidence, and unverified features are rejected. Minimum train and holdout sizes default to 100 games each. Seasons without enough prior training or holdout data are reported as skipped, not silently treated as validation.

## Run

```sh
python nba/availability_walk_forward.py \
  --input path/to/frozen-availability-ledger.json \
  --output /tmp/nba-availability-walk-forward.json
```

The result is a research candidate only. It always reports `independent_validation_passed: false`, `automatic_promotion_allowed: false`, and `production_probabilities_changed: false`. Before promotion, the ledger and protocol require independent review, adequate coverage across seasons/teams/statuses, a calibration review, and an untouched prospective holdout. Current daily NBA captures may not yet provide enough seasons for evaluation; if so the next implementation task is preserving the required point-in-time ledger rather than changing model percentages.
