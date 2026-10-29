# PULSO PLAYER NHL v5 — hybrid walk-forward

The hybrid combines prior-ten-game minutes / shot projections with prior-date contextual PULSO. Weights (0%, 25%, 50%, 75%, 100% contextual) are chosen on **previous-season predictions only**, based on MAE, and frozen for each target season. When previous-season scored predictions are unavailable, weights default to 50%.

Goals use predicted SOG and a Bayesian-smoothed **historical** goals-per-SOG ratio, with only games preceding the target date. It is a heuristic, not an identity: some credited NHL goals have zero recorded SOG. Goal probabilities are provisional Poisson count assumptions, evaluated with Brier and log loss.

Outputs: MAE for historical average, recent 5, recent 10, contextual, hybrid; binary metrics, per-team/position/season evaluation, ten calibration bins and full dated predictions.

## Execute
Merge PR only after green CI, open `PULSO PLAYER — NHL v5 hybrid walk-forward` under GitHub Actions, choose `main`, choose teams `EDM,COL,DAL,FLA,NYR,TOR` and run. Download artifact `pulso-player-nhl-v5-<run>`.

This remains retrospective historical player-participation evaluation, **not** independently captured pregame lineups and **not** official NHL ML/RT/+3 or a market signal. Never evaluate or use sportsbook odds in this engine.
