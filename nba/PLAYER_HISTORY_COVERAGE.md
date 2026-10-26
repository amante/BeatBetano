# NBA player-history coverage — PR #54

The daily workflow fetches a bounded sample of the **20 most recent completed
games** in the verified history ledger using ESPN game-summary boxscores.

Artifacts:
- `results/nba/player_game_history.json`: raw parsed player minutes, DNP and
  postgame starter labels, including per-game retrieval failures.
- `results/nba/player_history_coverage.json`: auditable coverage of the
  requested sample, counts of observed athlete rows and numeric minutes,
  incomplete two-team coverage, and explicit non-authorization for impact training.

The workflow skips the coverage report if the ESPN sampling step failed before
creating its JSON artifact. The sample fetch is nonblocking to allow unaffected
pregame baseline predictions to proceed.

**Limitations:** 20 games are NOT all historical NBA seasons. An ESPN boxscore
is evidence of *what happened*, not a trustworthy historical observation of
what was known before tipoff. We cannot use DNP retrospectively as the model's
pregame injury feature. No real pregame injury archive, causal loss-of-starter
estimator, independent walk-forward impact validation or official adjusted
probability is claimed by this stage. No odds inputs.

## Next data milestone

Obtain legally accessible, timestamped historical snapshots of NBA official
injury reports / lineups **published before tipoff**, crosswalk ESPN stable
player IDs and franchises, and measure sample coverage across full seasons.
Only after this can a fitted injury/replacement impact model be evaluated
chronologically on genuinely held-out games.
