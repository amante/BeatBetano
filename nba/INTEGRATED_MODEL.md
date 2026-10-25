# NBA integrated model — one candidate output, two mandatory layers

The full pregame runs as **one pipeline**:
1. First, compute immutable odds-free statistical baselines (Elo, Challenger, hybrid).
2. Second, verify source-cited starting lineups, injury status, replacement minutes and rotations, positional matchups, current team form, and schedule/rest/travel.
3. Third, require an *independently holdout-validated* log-odds adjustment from a recorded sporting-impact model. Combine its delta in **logit space** with the statistical hybrid baseline.
4. Publish a single `integrated_model.json`. `integrated_p_home` is deliberately **null** when verified sporting evidence or validated coefficients are missing. Keep baselines visible for diagnostics only; never label them final probabilities.

Every evidence field must have `verified: true`, a nonempty `source` and `observed_at_utc` dated no later than snapshot generation and strictly before game tipoff. Independently certified impact evidence additionally needs `log_odds_delta`, `calibration.independent_holdout_passed: true`, a `report_ref`, and `model_version`. These are schema checks, NOT proof that a claimed certification is genuine: independent audit of the underlying sources and coefficients remains necessary.

The GitHub workflow now creates `integrated_model.json` alongside the baseline and coverage status. **This is not yet a data-complete end-to-end forecast**: official injury feeds, full starting fives, minutes, matchups, and a validated impact model have not been connected. Until those are present, the final integrated probability remains null and betting eligibility false. No bookmaker odds enter the model. Do not imply the final model is calibrated merely because Python ran successfully.

For full daily slates, evaluate all games at the same depth. NFL untouched.
