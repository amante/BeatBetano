# Football base v0.1 — research only

Premier League, regulation plus stoppage time (home/draw/away). No extra time,
penalties, bookmaker prices, lineups or live deployment. This module does not
change PULSO or NHL. Pure Python standard library, Python 3.9+.

Run from repository root:

```sh
python -m unittest discover -s soccer/tests -v
python -m soccer.backtest --history reports/soccer/base-2026-11-02/history --output /tmp/football-backtest.json
```

The checked-in OpenFootball snapshots (CC0 source project:
https://github.com/openfootball/football.json) reproduce the first evaluation.
Their exact bytes are hashed in backtest.json. They were retrieved on 2026-11-02;
this is retrospective research, not proof of historical pregame capture. Upstream
master may change; always reproduce from these snapshots, not a fresh download.
Only full-time scores are accepted. Missing finals are skipped and completeness
checks then reject incomplete seasons. Duplicate fixtures and malformed scores fail.
Identity uses exact source team names: future source renames need explicit aliases.

The model fits league goal rate, home advantage and regularized team attack and
defence, with zero-mean team effects. Unknown teams get neutral league effects and
are flagged. Goal truncation loses less than 1e-8 probability mass. The optimizer
must converge. Prediction rejects dates on/before the latest training date.

Protocol fixed before the first backtest: train 2021-23, select regularization from
0.001/0.01/0.1 using 2023-24 log loss. Evaluate 2024-25 and 2025-26, with expanding
training strictly from previous seasons, frozen for each season. The second
holdout includes the first season's results in training under this fixed update
rule. Baseline is Laplace-smoothed historical home/draw/away frequency. Brier is
sum across three classes then mean across games; it is not the mean-class variant.

First results, 380 matches per season:

| Season | Poisson Brier | Frequency Brier | Poisson log loss | Frequency log loss |
|---|---:|---:|---:|---:|
| 2024-25 | 0.616906 | 0.656830 | 1.027177 | 1.082576 |
| 2025-26 | 0.629268 | 0.656169 | 1.044214 | 1.084457 |

Lower is better. Both seasons improve these descriptive metrics; this is not yet
an established statistical advantage. Each contains 38 games involving an unseen
team. Historical performance says nothing about betting profitability.

Next PRs, in order:
1. Calibration by class and paired uncertainty resampling whole matchdays; assess
   promoted-team performance and identity stability without retuning on holdouts.
2. A dated prospective capture contract: source timestamps, fixed cutoff, immutable
   forecasts and an official results adapter, then automatic football postmortems.
3. Publish experimental probabilities in PULSO with clear coverage and pending
   states. Collect prospective evidence before considering any model promotion.

No automatic retraining/promotion is enabled by this PR. No secret is required.
