# NFL Availability Delta 2.5: multi-season promotion gate

The new walk-forward evaluator refits models on prior years only, comparing EPA versus EPA + reported out-counts on identical eligible games. It reports paired Brier/log loss and cluster uncertainty for multiple holdout seasons. The model does **not** identify genuine starters, CB1/CB2/nickel coverage, replacement skill, or true target-game actives.

**Critical data constraint:** the current verified NFL injury ingestion covers only 2023–2024, not sufficient for a 3-season evaluation or reliable starter-return causal impact. The evaluator must refuse to generate a historical conclusion from incomplete years. No fabricated extra years, injury labels or backtest scores.

To execute when audited multiyear pregame features are available:
```
python validation/nfl_availability_walkforward.py --features FEATURES.csv --output results/walkforward
```
Input: season, game_id, home_win, five baseline EPA columns from nfl_epa.FEATURES, and 14 home_/away_ availability-count columns. Each row must reflect information observable before kickoff. Test on multiple independently held-out seasons and report coverage and subset selection. Promote only with significant, repeatable improvement and inspected calibration.
